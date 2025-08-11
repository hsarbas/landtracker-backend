def _unknown(s: str | None) -> str:
    if s is None:
        return "Unknown"
    s = s.strip()
    return s if s else "Unknown"


def _unknown_upper(s: str | None) -> str:
    return _unknown(s).upper()
