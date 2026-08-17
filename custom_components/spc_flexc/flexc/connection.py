"""Persistent FlexC transport client for SPC panels."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import zlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from Crypto.Cipher import AES
from homeassistant.const import CONF_HOST

from ..const import (
    CONF_COMMAND_PASSWORD,
    CONF_COMMAND_USERNAME,
    CONF_KEY,
    CONF_PORT,
    DEFAULT_PORT,
)
from .events import parse_event_payload
from .flexml import (
    build_alert_status_command,
    build_area_status_batch,
    build_flexc_ats_status_command,
    build_panel_summary_command,
    build_zone_status_batch,
    parse_alert_status,
    parse_area_status,
    parse_flexc_ats_status,
    parse_panel_summary,
    parse_zone_status,
)

_LOGGER = logging.getLogger(__name__)

INTERNAL_IV = bytes.fromhex("6D53436553737850436C656E46656900")

PROTOCOL_ID = 0x46
PROTOCOL_VERSION = 0x01

RCT_CONNECTION_ID = 0x77359401
INITIAL_RCT_SEQUENCE = 0x12345678
SPT_ACCOUNT = 0x00BC614E

MSG_CONNECTION_REQUEST_LEGACY = 0x00
MSG_CONNECTION_ACK_LEGACY = 0x01
MSG_CONNECTION_REQUEST = 0x02
MSG_CONNECTION_ACK = 0x03

MSG_POLL = 0x20
MSG_POLL_ACK = 0x21

MSG_EVENT = 0x60
MSG_EVENT_ACK = 0x61

MSG_DATA = 0x80
MSG_DATA_ACK = 0x81

MSG_ERROR = 0xFF

CONNECT_TIMEOUT = 30.0
COMMAND_TIMEOUT = 15.0
MAX_FRAME_LENGTH = 65536


class FlexCError(Exception):
    """Base FlexC exception."""


class FlexCConnectionError(FlexCError):
    """FlexC connection error."""


class FlexCProtocolError(FlexCError):
    """FlexC protocol error."""


class FlexCCommandError(FlexCError):
    """SPC rejected a FlexC command."""


def _be16(value: bytes) -> int:
    return int.from_bytes(value, "big")


def _be32(value: bytes) -> int:
    return int.from_bytes(value, "big")


def _put16(value: int) -> bytes:
    return int(value).to_bytes(2, "big")


def _put32(value: int) -> bytes:
    return int(value & 0xFFFFFFFF).to_bytes(4, "big")


class FlexCClient:
    """Persistent FlexC receiver/client.

    The SPC acts as the TCP client and connects to Home Assistant.
    Home Assistant therefore listens on the configured FlexC port.
    """

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Initialize the FlexC client."""
        self.host = str(config[CONF_HOST])
        self.port = int(config.get(CONF_PORT, DEFAULT_PORT))

        key_value = config[CONF_KEY]

        if isinstance(key_value, bytes):
            self._key = key_value
        else:
            try:
                self._key = bytes.fromhex(str(key_value))
            except ValueError as err:
                raise ValueError("FlexC encryption key must be hexadecimal") from err

        if len(self._key) != 32:
            raise ValueError("FlexC encryption key must contain exactly 32 bytes")

        self.command_username = str(config[CONF_COMMAND_USERNAME])
        self.command_password = str(config[CONF_COMMAND_PASSWORD])

        self.connected = False

        self._server: asyncio.AbstractServer | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        self._connected_event = asyncio.Event()
        self._closed = False

        self._connection_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()

        self._last_message: dict[str, Any] | None = None
        self._rct_sequence = INITIAL_RCT_SEQUENCE

        self._pending_reply: asyncio.Future[str] | None = None
        self._poll_waiter: asyncio.Future[dict[str, Any]] | None = None
        self._response_buffer = bytearray()
        self._response_length: int | None = None

        self._event_callback: Callable[[dict[str, str]], None] | None = None

    async def async_ensure_connected(self) -> None:
        """Ensure that the SPC has established a FlexC session."""
        if self.connected and self._writer is not None:
            return

        async with self._connection_lock:
            if self.connected and self._writer is not None:
                return

            if self._server is None:
                await self._start_server()

        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                await self._connected_event.wait()
        except TimeoutError as err:
            raise FlexCConnectionError(
                f"SPC {self.host} did not connect to FlexC port "
                f"{self.port} within {CONNECT_TIMEOUT:.0f}s"
            ) from err

    async def _start_server(self) -> None:
        """Start the local FlexC TCP receiver."""
        if self._closed:
            raise FlexCConnectionError("FlexC client is closed")

        self._server = await asyncio.start_server(
            self._handle_client,
            host="0.0.0.0",
            port=self.port,
        )

        sockets: tuple[Any, ...] = tuple(self._server.sockets or ())
        listeners = ", ".join(str(sock.getsockname()) for sock in sockets)

        _LOGGER.info(
            "FlexC receiver listening on %s for SPC %s",
            listeners,
            self.host,
        )

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle one SPC FlexC TCP connection."""
        peer = writer.get_extra_info("peername")
        peer_host = str(peer[0]) if peer else ""

        if self.host and peer_host != self.host:
            _LOGGER.warning(
                "Rejecting FlexC connection from unexpected host %s (expected %s)",
                peer_host,
                self.host,
            )
            writer.close()
            await writer.wait_closed()
            return

        if self._writer is not None and self._writer is not writer:
            _LOGGER.warning(
                "Replacing existing FlexC connection with new connection from %s",
                peer_host,
            )
            self._writer.close()

        self._reader = reader
        self._writer = writer

        _LOGGER.info("SPC FlexC TCP connection accepted from %s", peer_host)

        try:
            while not self._closed:
                frame = await self._read_frame(reader)
                message = self._parse_frame(frame)

                if not message["sha1_ok"]:
                    _LOGGER.warning(
                        "Ignoring FlexC message 0x%02X with invalid SHA-1",
                        message["message_id"],
                    )
                    continue

                self._last_message = message
                self._rct_sequence = message["rct_sequence"]

                await self._handle_message(message)

        except asyncio.IncompleteReadError as err:
            if err.partial:
                _LOGGER.warning(
                    "FlexC connection lost with partial frame: %s",
                    err,
                )
            else:
                _LOGGER.debug("FlexC connection closed by peer")

        except (ConnectionError, OSError) as err:
            _LOGGER.warning("FlexC connection lost: %s", err)

        except asyncio.CancelledError:
            raise

        except Exception:
            _LOGGER.exception("Unexpected FlexC receiver error")

        finally:
            if self._writer is writer:
                self._reader = None
                self._writer = None
                self.connected = False
                self._connected_event.clear()

                if self._pending_reply is not None and not self._pending_reply.done():
                    self._pending_reply.set_exception(
                        FlexCConnectionError(
                            "FlexC connection closed while waiting for a reply"
                        )
                    )

                self._pending_reply = None

            writer.close()

            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _read_frame(
        self,
        reader: asyncio.StreamReader,
    ) -> bytes:
        """Read one complete FlexC frame."""
        header = await reader.readexactly(16)

        if header[0] != PROTOCOL_ID:
            raise FlexCProtocolError(f"Unexpected FlexC protocol ID 0x{header[0]:02X}")

        if header[1] != PROTOCOL_VERSION:
            raise FlexCProtocolError(f"Unexpected FlexC version 0x{header[1]:02X}")

        length_units = _be16(header[2:4])

        # Empirically validated:
        # wire length = 64 + (length_units * 16)
        total_length = 64 + length_units * 16

        if (
            total_length < 64
            or total_length > MAX_FRAME_LENGTH
            or (total_length - 16) % 16
        ):
            raise FlexCProtocolError(f"Invalid FlexC frame length {total_length}")

        body = await reader.readexactly(total_length - 16)

        return header + body

    def _parse_frame(self, frame: bytes) -> dict[str, Any]:
        """Decrypt and parse one FlexC frame."""
        if len(frame) < 64 or (len(frame) - 16) % 16:
            raise FlexCProtocolError(
                f"Invalid encrypted FlexC frame length {len(frame)}"
            )

        clear = frame[:16]

        plaintext = AES.new(
            self._key,
            AES.MODE_CBC,
            INTERNAL_IV,
        ).decrypt(frame[16:])

        data_header = plaintext[20:28]

        message: dict[str, Any] = {
            "wire": frame,
            "clear": clear,
            "plain": plaintext,
            "protocol_id": clear[0],
            "version": clear[1],
            "length_units": _be16(clear[2:4]),
            "connection_id": _be32(clear[4:8]),
            "spt_sequence": _be32(plaintext[0:4]),
            "rct_sequence": _be32(plaintext[4:8]),
            "spt_account": _be32(plaintext[8:12]),
            "rct_identifier": _be32(plaintext[12:16]),
            "reserved_20_21": plaintext[16:18],
            "message_id": plaintext[18],
            "reserved_23": plaintext[19],
            "data_header": data_header,
            "recv_sha1": plaintext[28:48],
            "app_data": plaintext[48:],
            "application_length": _be32(data_header[0:4]),
            "new_application_message": data_header[4] == 1,
        }

        logical = bytearray(clear + plaintext)
        logical[44:64] = b"\x00" * 20

        message["calc_sha1"] = hashlib.sha1(logical).digest()
        message["sha1_ok"] = message["recv_sha1"] == message["calc_sha1"]

        return message

    async def async_get_flexc_ats_status(
        self,
        ats_id: int,
    ) -> dict[str, Any]:
        """Request and return instantaneous FlexC ATS status."""
        command = build_flexc_ats_status_command(
            ats_id,
            self.command_username,
            self.command_password,
        )

        response = await self.async_send_flexml(command)

        return parse_flexc_ats_status(response)

    @staticmethod
    def _digest_for(
        clear: bytes,
        plaintext: bytes | bytearray,
    ) -> bytes:
        """Calculate the validated FlexC SHA-1 digest."""
        logical = bytearray(clear + bytes(plaintext))
        logical[44:64] = b"\x00" * 20
        return hashlib.sha1(logical).digest()

    def _encrypt_message(
        self,
        clear: bytes,
        plaintext: bytes | bytearray,
    ) -> bytes:
        """Insert SHA-1 and AES encrypt a FlexC message."""
        plain = bytearray(plaintext)

        plain[28:48] = b"\x00" * 20
        plain[28:48] = self._digest_for(clear, plain)

        ciphertext = AES.new(
            self._key,
            AES.MODE_CBC,
            INTERNAL_IV,
        ).encrypt(bytes(plain))

        return clear + ciphertext

    def _build_connection_ack(
        self,
        request: Mapping[str, Any],
    ) -> bytes:
        """Build legacy CONNECTION_ACK 0x01."""
        clear = bytearray(16)

        clear[0] = request["protocol_id"]
        clear[1] = request["version"]
        clear[2:4] = _put16(0)
        clear[4:8] = _put32(RCT_CONNECTION_ID)

        plain = bytearray(48)

        plain[0:4] = _put32(request["spt_sequence"])
        plain[4:8] = _put32(INITIAL_RCT_SEQUENCE)
        plain[8:12] = _put32(SPT_ACCOUNT)
        plain[12:16] = _put32(request["rct_identifier"])

        plain[18] = MSG_CONNECTION_ACK_LEGACY
        plain[20:28] = request["data_header"]

        return self._encrypt_message(bytes(clear), plain)

    def _build_clone_ack(
        self,
        request: Mapping[str, Any],
        reply_id: int,
    ) -> bytes:
        """Build a zero-application ACK cloning session fields."""
        clear = bytearray(request["clear"])
        clear[2:4] = _put16(0)

        plain = bytearray(48)

        # These semantics were validated against the SPC:
        # preserve sptSequence exactly.
        plain[0:4] = _put32(request["spt_sequence"])
        plain[4:8] = _put32(request["rct_sequence"])
        plain[8:12] = _put32(request["spt_account"])
        plain[12:16] = _put32(request["rct_identifier"])

        plain[18] = reply_id
        plain[20:28] = request["data_header"]

        return self._encrypt_message(bytes(clear), plain)

    def _build_application_buffer(self, command: str) -> bytes:
        """Build the FLEXML application buffer exactly as tested."""
        try:
            command_bytes = command.encode("ascii")
        except UnicodeEncodeError as err:
            raise FlexCProtocolError(
                "FLEXML command must be ASCII serializable"
            ) from err

        xml_length = len(command_bytes)
        xml_crc = zlib.crc32(command_bytes) & 0xFFFFFFFF

        header_xml = (
            '<FLEXML XML_COMPRESS="0" '
            f'XML_CLEN="{xml_length}" '
            f'XML_LEN="{xml_length}" '
            f'XML_CRC="{xml_crc}" '
            'BIN_LEN="0" BIN_CRC="0" />'
        )

        raw = header_xml.encode("ascii") + b"\x00" + command_bytes + b"\x00"

        aligned_length = ((len(raw) + 15) // 16) * 16

        # The validated SPCLink-compatible implementation leaves
        # non-application alignment bytes non-zero/random.
        application = bytearray(os.urandom(aligned_length))
        application[: len(raw)] = raw

        return bytes(application)

    def _build_outbound_data(
        self,
        last_message: Mapping[str, Any],
        rct_sequence: int,
        application: bytes,
    ) -> bytes:
        """Build outbound DATA 0x80."""
        clear = bytearray(16)

        clear[0] = last_message["protocol_id"]
        clear[1] = last_message["version"]
        clear[2:4] = _put16(len(application) // 16)
        clear[4:8] = _put32(last_message["connection_id"])

        plain = bytearray(48 + len(application))

        plain[0:4] = _put32(last_message["spt_sequence"])
        plain[4:8] = _put32(rct_sequence)
        plain[8:12] = _put32(last_message["spt_account"])
        plain[12:16] = _put32(last_message["rct_identifier"])

        plain[18] = MSG_DATA

        # SendData() semantics validated by the successful zone and
        # PANEL_SUMMARY tests.
        plain[20:24] = _put32(len(application))
        plain[24] = 1
        plain[25:28] = b"\x00\x00\x00"

        plain[48:] = application

        return self._encrypt_message(bytes(clear), plain)

    async def _send_wire(self, wire: bytes) -> None:
        """Send one FlexC wire frame."""
        writer = self._writer

        if writer is None or writer.is_closing():
            raise FlexCConnectionError("No active FlexC TCP connection")

        writer.write(wire)
        await writer.drain()

    async def _handle_message(
        self,
        message: Mapping[str, Any],
    ) -> None:
        """Process one validated incoming FlexC message."""
        message_id = int(message["message_id"])

        if message_id == MSG_CONNECTION_REQUEST_LEGACY:
            await self._send_wire(self._build_connection_ack(message))

            self._rct_sequence = INITIAL_RCT_SEQUENCE
            self.connected = True
            self._connected_event.set()

            _LOGGER.info("FlexC legacy connection handshake completed")
            return

        if message_id == MSG_CONNECTION_REQUEST:
            await self._send_wire(
                self._build_clone_ack(
                    message,
                    MSG_CONNECTION_ACK,
                )
            )

            self.connected = True
            self._connected_event.set()

            _LOGGER.info("FlexC connection handshake completed")
            return

        if message_id == MSG_POLL:
            await self._send_wire(
                self._build_clone_ack(
                    message,
                    MSG_POLL_ACK,
                )
            )

            self.connected = True
            self._connected_event.set()

            poll_waiter = self._poll_waiter

            if poll_waiter is not None and not poll_waiter.done():
                poll_waiter.set_result(dict(message))

            return

        if message_id == MSG_EVENT:
            await self._send_wire(
                self._build_clone_ack(
                    message,
                    MSG_EVENT_ACK,
                )
            )

            event = parse_event_payload(bytes(message["app_data"]))

            if event is not None:
                callback = self._event_callback

                if callback is not None:
                    callback(event)

            return

        if message_id == MSG_DATA_ACK:
            # ACK for our outbound FLEXML DATA command.
            return

        if message_id == MSG_DATA:
            await self._send_wire(
                self._build_clone_ack(
                    message,
                    MSG_DATA_ACK,
                )
            )

            self._handle_incoming_data(message)
            return

        if message_id == MSG_ERROR:
            self._handle_error(message)
            return

        _LOGGER.debug(
            "Unhandled valid FlexC message 0x%02X",
            message_id,
        )

    def _handle_incoming_data(
        self,
        message: Mapping[str, Any],
    ) -> None:
        """Reassemble an incoming FlexC application message."""
        if self._pending_reply is None:
            _LOGGER.debug("Received unsolicited DATA 0x80 with no pending request")
            return

        if message["new_application_message"]:
            self._response_buffer = bytearray()
            self._response_length = int(message["application_length"])

        if self._response_length is None:
            _LOGGER.warning("Received FlexC DATA without application length")
            return

        app_data = bytes(message["app_data"])

        self._response_buffer.extend(app_data)

        if len(self._response_buffer) < self._response_length:
            return

        logical = bytes(self._response_buffer[: self._response_length])

        _LOGGER.debug(
            "FlexC DATA reply: logical_length=%d received=%d",
            self._response_length,
            len(self._response_buffer),
        )

        try:
            response = self._decode_application(logical)
        except FlexCProtocolError as err:
            pending = self._pending_reply

            if pending is not None and not pending.done():
                pending.set_exception(err)

            return

        pending = self._pending_reply

        if pending is not None and not pending.done():
            pending.set_result(response)

    @staticmethod
    def _decode_application(application: bytes) -> str:
        """Extract FLEXML_REPLY from an application buffer."""
        xml_parts: list[str] = []

        for raw_part in application.split(b"\x00"):
            raw_part = raw_part.strip()

            if not raw_part.startswith(b"<"):
                continue

            try:
                text = raw_part.decode("utf-8")
            except UnicodeDecodeError:
                continue

            xml_parts.append(text)

        for xml_part in xml_parts:
            if xml_part.startswith("<FLEXML_REPLY"):
                return xml_part

        _LOGGER.warning(
            "FlexC DATA without FLEXML_REPLY: xml_parts=%r raw=%s",
            xml_parts,
            application.hex(" "),
        )

        raise FlexCProtocolError("FlexC DATA reply contained no FLEXML_REPLY")

    def _handle_error(
        self,
        message: Mapping[str, Any],
    ) -> None:
        """Handle a FlexC ERROR 0xFF."""
        header = bytes(message["data_header"])

        # The second half of dataHeader carried the compact error
        # indication in the diagnostics already captured.
        error_code = _be32(header[4:8])

        error = FlexCCommandError(
            "SPC returned FlexC ERROR 0xFF "
            f"(dataHeader={header.hex(' ').upper()}, "
            f"code=0x{error_code:08X})"
        )

        pending = self._pending_reply

        if pending is not None and not pending.done():
            pending.set_exception(error)
        else:
            _LOGGER.warning("%s", error)

    async def async_send_flexml(self, command: str) -> str:
        """Send one FLEXML command and return FLEXML_REPLY."""
        await self.async_ensure_connected()

        async with self._command_lock:
            loop = asyncio.get_running_loop()

            # Wait for a fresh SPC POLL 0x20 before emitting DATA 0x80.
            # This matches the sequence validated by the working prototypes.
            poll_waiter: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._poll_waiter = poll_waiter

            try:
                async with asyncio.timeout(COMMAND_TIMEOUT):
                    poll_message = await poll_waiter

            except TimeoutError as err:
                raise FlexCConnectionError(
                    "Timeout waiting for FlexC POLL 0x20"
                ) from err

            finally:
                if self._poll_waiter is poll_waiter:
                    self._poll_waiter = None

            pending: asyncio.Future[str] = loop.create_future()

            self._pending_reply = pending
            self._response_buffer = bytearray()
            self._response_length = None

            application = self._build_application_buffer(command)

            self._rct_sequence = (int(poll_message["rct_sequence"]) + 1) & 0xFFFFFFFF

            wire = self._build_outbound_data(
                poll_message,
                self._rct_sequence,
                application,
            )

            try:
                await self._send_wire(wire)

                async with asyncio.timeout(COMMAND_TIMEOUT):
                    return await pending

            except TimeoutError as err:
                self.connected = False
                self._connected_event.clear()

                writer = self._writer
                self._writer = None
                self._reader = None

                if writer is not None:
                    writer.close()

                    try:
                        await writer.wait_closed()
                    except (ConnectionError, OSError):
                        pass

                raise FlexCCommandError(
                    "Timeout waiting for FlexC FLEXML reply"
                ) from err

            finally:
                if self._pending_reply is pending:
                    self._pending_reply = None

                self._response_buffer = bytearray()
                self._response_length = None

    async def async_get_panel_summary(
        self,
    ) -> dict[str, str]:
        """Request and return PANEL_SUMMARY."""
        command = build_panel_summary_command(
            self.command_username,
            self.command_password,
        )

        response = await self.async_send_flexml(command)

        return parse_panel_summary(response)

    def set_event_callback(
        self,
        callback: Callable[[dict[str, str]], None] | None,
    ) -> None:
        """Set the callback invoked for validated EVENT 0x60 messages."""
        self._event_callback = callback

    async def async_get_alert_status(
        self,
    ) -> list[dict[str, str]]:
        """Read current panel alerts."""
        command = build_alert_status_command(
            self.command_username,
            self.command_password,
        )

        response = await self.async_send_flexml(command)

        return parse_alert_status(response)

    async def async_get_area_status(
        self,
        area_ids: Iterable[int],
    ) -> list[dict[str, str]]:
        """Request statuses for a collection of SPC areas."""
        command = build_area_status_batch(
            area_ids,
            self.command_username,
            self.command_password,
        )

        response = await self.async_send_flexml(command)

        return parse_area_status(response)

    async def async_get_zone_status(
        self,
        zone_ids: Iterable[int],
    ) -> list[dict[str, str]]:
        """Request statuses for a collection of SPC zones."""
        command = build_zone_status_batch(
            zone_ids,
            self.command_username,
            self.command_password,
        )

        response = await self.async_send_flexml(command)

        return parse_zone_status(response)

    async def async_close(self) -> None:
        """Close the FlexC receiver and current SPC connection."""
        self._closed = True
        self.connected = False
        self._connected_event.clear()

        if self._pending_reply is not None and not self._pending_reply.done():
            self._pending_reply.set_exception(
                FlexCConnectionError("FlexC client closed")
            )

        self._pending_reply = None

        writer = self._writer
        self._writer = None
        self._reader = None

        if writer is not None:
            writer.close()

            try:
                await writer.wait_closed()
            except OSError:
                pass

        server = self._server
        self._server = None

        if server is not None:
            server.close()
            await server.wait_closed()
