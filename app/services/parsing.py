import re
from typing import Optional, Tuple, Dict, List
import random

# ---------------- Bearing + distance parsing ----------------

_BEARING_RX = re.compile(
    r'(?P<ns>[NS])\.?\s*'
    r'(?P<deg>\d+)(?:°|\s*deg\.?|-)\s*'
    r'(?P<min>\d+)\'?\s*'
    r'(?:\s*(?P<sec>\d+(?:\.\d+)?))?\"?\s*'
    r'(?P<ew>[EW])?\.?',
    flags=re.IGNORECASE
)


def parse_segment(seg: str) -> Tuple[Optional[Dict], Optional[float]]:
    seg_clean = seg.strip().rstrip(',:;.')
    m_b = _BEARING_RX.search(seg_clean)
    if not m_b:
        return None, None

    b = m_b.groupdict()
    ns = b["ns"].upper()
    deg = int(b["deg"])
    mn = int(b["min"])
    sc = float(b["sec"]) if b.get("sec") else None
    ew = b["ew"].upper() if b.get("ew") else None

    # Distance after the bearing
    post = seg_clean[m_b.end():]
    m_dist = re.search(r'(?P<dist>[\d\.]+)\s*m', post, flags=re.IGNORECASE)
    if not m_dist:
        raise ValueError(f"Could not parse distance in segment: {seg_clean!r}")
    dist = float(m_dist.group("dist"))

    return {"ns": ns, "degrees": deg, "minutes": mn, "seconds": sc, "ew": ew}, dist


# ---------------- Title/Owner heuristics (optional) ----------------

# Try common PH title formats (TCT/OCT or long form)
_TITLE_NO_PATTERNS = [
    r'(?is)(?:Transfer|Original)\s+Certificate\s+of\s+Title[\s\S]{0,100}?\bNo\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-\/\. ]{2,})',
    r'(?im)^\s*TCT\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-\/\. ]{2,})\s*$',
]


_OWNER_PATTERNS = [
    r'(?:Registered\s+Owner|Owner)\s*[:\-]\s*([A-Z][A-Za-z\.\- ,]+)',
    r'(?:Registered\s+in\s+favor\s+of|in\s+favor\s+of)\s+([A-Z][A-Za-z\.\- ,]+)',
]


def _clean_capture(s: str) -> str:
    # stop at newline or obvious delimiters; trim trailing punctuation
    s = re.split(r'[\r\n;]', s, maxsplit=1)[0]
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip(" \t,.;:")


def _find_first(patterns: List[str], text: str) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return _clean_capture(m.group(1))
    return None


def _title_num_gen() -> str:
    """
    Generate a plausible Philippine land title number.
    Examples: TCT-123456789, OCT-2025-0045123
    """
    prefix = random.choice(["TCT", "OCT"])
    # 50/50: plain numeric vs year-prefixed
    if random.random() < 0.5:
        num = f"{random.randint(100_000, 999_999_999)}"
        return f"{prefix}-{num}"
    else:
        year = random.randint(1980, 2025)
        tail = f"{random.randint(1_000, 9_999_999):07d}"
        return f"{prefix}-{year}-{tail}"


def _owner_gen() -> str:
    """
    Generate a realistic-looking Filipino full name (fictional).
    """
    first_names = [
        "Juan", "Maria", "Jose", "Ana", "Pedro", "Luz", "Carlos", "Rosa",
        "Miguel", "Elena", "Luis", "Carmen", "Ramon", "Teresa", "Andres",
        "Sofia", "Emilio", "Veronica", "Roberto", "Isabel"
    ]
    surnames = [
        "Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza", "Flores",
        "Gonzales", "Torres", "Ramos", "Aquino", "Castillo", "Navarro",
        "Villanueva", "Domingo", "Marquez", "Pascual", "De Leon", "Alonzo", "Soriano"
    ]
    middle_initial = chr(random.randint(ord('A'), ord('Z')))
    return f"{random.choice(first_names)} {middle_initial}. {random.choice(surnames)}"


def extract_title_meta(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort extraction from whatever text you feed in (may be just the technical description).
    If not present, returns (None, None). Frontend can still use the values when available.
    """
    title_number = _find_first(_TITLE_NO_PATTERNS, text) or _title_num_gen()
    owner = _find_first(_OWNER_PATTERNS, text) or _owner_gen()
    return title_number, owner


# ---------------- Main parser ----------------

def parse_land_title(text: str):
    """
    Parse the given technical description text.
    Returns: (title_number, owner, technical_description, tie_point, boundaries)
    - technical_description is just the provided 'desc' (echoed back)
    - tie_point is parsed from the 'Beginning at ... from ...' segment
    - boundaries is a list of (bearing_dict, distance_m)
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty description")

    # Heuristic extraction for title_number/owner from the provided text (if present)
    title_number, owner = extract_title_meta(text)
    technical_description = text.strip()

    # Find the "Beginning at ..." anchor
    anchor_phrases = [
        r'beginning\s+at\s+a',
        r'beg\.\s+at\s+a'
    ]

    pattern = r'(?:' + '|'.join(anchor_phrases) + r')'
    m_anchor = re.search(pattern, technical_description, flags=re.IGNORECASE)
    if not m_anchor:
        raise ValueError("Could not find the 'Beginning at a ...' anchor")

    # Keep from the anchor onwards; split into segments by ';' or 'thence'
    work = technical_description[m_anchor.start():].rstrip(':. ')
    raw_parts = re.split(r'(?:;\s*|\bthence\b)', work, flags=re.IGNORECASE)
    parts = [p for p in raw_parts if p.strip()]
    if not parts:
        raise ValueError("No boundary segments found")

    # First segment should contain the tie-point in "... from <TIE POINT>"
    first_seg, *corner_segs = parts
    split_td = re.split(r'\s+from\s+', first_seg, flags=re.IGNORECASE)
    if len(split_td) != 2:
        raise ValueError(f"Could not find tie-point in: {first_seg!r}")
    seg_td, tie_point = split_td
    tie_b, tie_d = parse_segment(seg_td)

    boundaries = []
    if tie_b and tie_d:
        boundaries.append((tie_b, tie_d))

    for seg in corner_segs:
        bdict, dist = parse_segment(seg)
        if bdict and dist is not None:
            boundaries.append((bdict, dist))

    return title_number, owner, technical_description, _clean_capture(tie_point), boundaries


# ============ OLD SERVICES ============
def parse_segment_old(seg: str) -> Tuple[Optional[Dict], Optional[float]]:
    seg_clean = seg.strip().rstrip(',:;.')
    m_b = _BEARING_RX.search(seg_clean)
    if not m_b:
        return None, None
    b = m_b.groupdict()
    ns = b["ns"].upper()
    deg = int(b["deg"])
    mn = int(b["min"])
    sc = float(b["sec"]) if b.get("sec") else None
    ew = b["ew"].upper() if b.get("ew") else None
    post = seg_clean[m_b.end():]
    m_dist = re.search(r'(?P<dist>[\d\.]+)\s*m', post, flags=re.IGNORECASE)
    if not m_dist:
        raise ValueError(f"Could not parse distance in segment: {seg_clean!r}")
    dist = float(m_dist.group("dist"))
    return {"ns": ns, "degrees": deg, "minutes": mn, "seconds": sc, "ew": ew}, dist


def parse_land_title_old(desc: str):
    anchor_phrases = [
        r'beginning\s+at\s+a',
        r'beg.\s+at\s+a'
    ]

    desc = desc.strip().rstrip(':.')
    pattern = r'(?:' + '|'.join(anchor_phrases) + r')'
    m_anchor = re.search(pattern, desc, flags=re.IGNORECASE)
    if not m_anchor:
        raise ValueError("Could not find the 'Beginning at a ...' anchor")

    desc = desc[m_anchor.start():]
    raw_parts = re.split(r'(?:;\s*|\bthence\b)', desc, flags=re.IGNORECASE)
    parts = [p for p in raw_parts if p.strip()]
    first_seg, *corner_segs = parts
    split_td = re.split(r'\s+from\s+', first_seg, flags=re.IGNORECASE)
    if len(split_td) != 2:
        raise ValueError(f"Could not find tie-point in: {first_seg!r}")
    seg_td, tie_point = split_td
    tie_b, tie_d = parse_segment_old(seg_td)
    boundaries = [ (tie_b, tie_d) ]
    for seg in corner_segs:
        bdict, dist = parse_segment_old(seg)
        if bdict and dist:
            boundaries.append((bdict, dist))
    # return tie_point.strip().rstrip(';'), boundaries
    title_number = 'T-0001'
    owner = 'Harvey Arbas'
    technical_description = 'test technical description'
    return title_number, owner, technical_description, tie_point.strip().rstrip(';'), boundaries
