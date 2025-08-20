from typing import Optional


def norm_str(s: Optional[str]) -> Optional[str]:
    if isinstance(s, str):
        s = s.strip()
        return s or None
    return None


def norm_upper(s: Optional[str]) -> Optional[str]:
    s = norm_str(s)
    return s.upper() if s is not None else None
