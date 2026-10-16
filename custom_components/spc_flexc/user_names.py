"""Safe SPC user display-name resolution helpers."""

from collections.abc import Mapping


def parse_user_aliases(text: str) -> dict[str, str]:
    """Parse ID=name lines without accepting credentials or arbitrary keys."""
    aliases: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError("Expected USER_ID=Display name")
        user_id, name = (part.strip() for part in line.split("=", 1))
        if not user_id.isdecimal() or not name or len(name) > 100:
            raise ValueError("Invalid user alias")
        aliases[str(int(user_id))] = name
    return aliases


def display_user_name(
    user_id: int | None,
    raw_name: str | None,
    aliases: Mapping[str, str],
    discovered: Mapping[int, str] | None = None,
) -> str | None:
    """Prefer an explicit alias, then the panel user name, then event text."""
    if user_id is None:
        return raw_name
    return (
        aliases.get(str(user_id))
        or (discovered or {}).get(user_id)
        or raw_name
    )
