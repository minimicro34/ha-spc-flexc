"""Persistent FlexC client skeleton.

This file intentionally does not fake a working protocol implementation.
Port the exact validated handshake/frame/sequence/AES/SHA1 code from the
prototype scripts here before installing on a production alarm panel.
"""


class FlexCClient:
    def __init__(self, config):
        self.config = config
        self.connected = False

    async def async_ensure_connected(self):
        # TODO: persistent TCP server/session:
        # 0x02->0x03, 0x20->0x21, 0x60->0x61, DATA 0x80/0x81,
        # sequence handling, reconnection and FLEXML reassembly.
        raise NotImplementedError(
            "FlexC transport must be ported from validated prototype"
        )

    async def async_get_panel_summary(self):
        return None

    async def async_close(self):
        self.connected = False
