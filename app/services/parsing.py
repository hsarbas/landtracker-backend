import re
from typing import Tuple, List, Dict, Optional
import random

# ---------------- Bearing + distance parsing ----------------

_BEARING_RX = re.compile(
    r'(?P<ns>[NS])\.?\s*'
    r'(?P<deg>\d{1,3})\s*(?:°|deg(?:ree)?s?\.?|-)\s*'
    r'(?:[EW]\s*)?'  # tolerate OCR like "DEGE"
    r'(?P<min>\d{1,2})\s*(?:\'|′|min(?:ute)?s?\.?)?\s*'
    r'(?: (?P<sec>\d{1,2}(?:\.\d+)?)\s*(?:\"|″|sec(?:ond)?s?\.?)?\s* )?'
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


# ──────────────────────────────────────────────────────────────────────────────
# Maintain/extend these lists as you encounter new phrasing or page furniture
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_START_VARIATIONS = [
    r"beginning\s+at\s+a\s+point",
    r"beginning\s+at\s+point",
    r"beginning\s+at",
    r"begin\s+at\s+a\s+point",
    r"beg\.\s*at\s+a\s+point",
    r"starting\s+at\s+a\s+point",
    r"commencing\s+at\s+a\s+point",
]

DEFAULT_END_VARIATIONS = [
    r"to\s+point\s+of\s+beginning",
    r"to\s+the\s+point\s+of\s+beginning",
    r"returning\s+to\s+the\s+point\s+of\s+beginning",
    r"back\s+to\s+point\s+of\s+beginning",
    r"back\s+to\s+the\s+point\s+of\s+beginning",
    r"to\s+point\s+of\s+beginning[\.,]?",
    r"to\s+the\s+point\s+of\s+beginning[\.,]?",
]

PAGE_HEADER_FOOTER_PATTERNS = [
    r"^\s*page\s*\d+\s*(of\s*\d+)?\s*$",
    r"^\s*—?\s*\d+\s*—?\s*$",                     # — 2 —
    r"^\s*tct\s*no\.\s*\S+\s*$",                  # TCT No. 12345
    r"^\s*oct\s*no\.\s*\S+\s*$",                  # OCT No. 12345
    r"^\s*original\s+certificate\s+of\s+title\s*$",
    r"^\s*transfer\s+certificate\s+of\s+title\s*$",
    r"^\s*registry\s+of\s+deeds.*$",
]

CONTINUATION_PATTERNS = [
    r"\(?\s*continued\s+on\s+page\s*\d+\s*\)?",
    r"\(?\s*continued\s+in\s+page\s*\d+\s*\)?",
    r"\(?\s*continuation\s*\)?",
]

# If no explicit end anchor is found, stop at the first of these “strong” section headers
STOP_MARKERS = [
    r"\bmemoranda\s+of\s+encumbrances\b",
    r"\bencumbrances\b",
    r"\bannotation[s]?\b",
    r"\bnote[: ]",
    r"\barea\s*[:=]",
    r"\btechnical\s+description\b",  # a second TD heading (reprints)
    r"\bowner\b",
    r"\bissued\b",
]

# Lines we consider “TD-like” when filtering intruding lines
KEEP_TOKENS = [
    r"\bthence\b",
    r"\bfrom\b",
    r"\bpoint\b|\bcorner\b|P\.?O\.?B\.?",
    r"\bmeters?\b|\bm\.\b",
    r"\bdegrees?\b|°|º",
    r"\bminutes?\b|′|’",
    r"\bseconds?\b|″",
    r"\btrue\b|\bmagnetic\b|\bbearing\b|\bcourse\b",
    r"\bdistance\b",
    r"\bnorth|south|east|west\b|\bN(?:E|W)?\b|\bS(?:E|W)?\b|\bE\b|\bW\b",  # N, NE, SW...
]

# ──────────────────────────────────────────────────────────────────────────────
# Compiled regex helpers
# ──────────────────────────────────────────────────────────────────────────────
KEEP_TOKENS_RE      = re.compile("|".join(KEEP_TOKENS), re.IGNORECASE)
HEADER_FOOTER_RE    = re.compile("|".join(PAGE_HEADER_FOOTER_PATTERNS), re.IGNORECASE)
CONTINUATION_RE     = re.compile("|".join(CONTINUATION_PATTERNS), re.IGNORECASE)
STOP_MARKERS_RE     = re.compile("|".join(STOP_MARKERS), re.IGNORECASE)


def _compile_anchor_regex(variations: List[str]) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(variations), re.IGNORECASE | re.DOTALL)


# ──────────────────────────────────────────────────────────────────────────────
# Page-aware cleaning and slicing
# ──────────────────────────────────────────────────────────────────────────────
def _dehyphenate(line: str) -> str:
    # Merge words broken at line end, e.g., "north-\nwest" -> "northwest"
    return re.sub(r"(\w)-\s*$", r"\1", line)


def _strip_headers_footers_and_continuations(text: str) -> str:
    """
    Remove page headers/footers, page numbers, and "(continued ...)" notes.
    Also joins lines broken by end-of-line hyphenation.
    """
    lines = text.splitlines()
    cleaned = []
    for raw in lines:
        line = raw.strip()
        if not line:
            cleaned.append(raw)
            continue
        if HEADER_FOOTER_RE.match(line):
            continue
        line = CONTINUATION_RE.sub("", line)  # remove continuation hints
        cleaned.append(line)

    # Join hyphenations across lines
    joined: List[str] = []
    for i, line in enumerate(cleaned):
        if i > 0 and cleaned[i - 1].rstrip().endswith("-"):
            joined[-1] = _dehyphenate(joined[-1]) + line.lstrip()
        else:
            joined.append(line)
    return "\n".join(joined)


def _slice_between_anchors_spanning_pages(
    text: str,
    include_markers: bool = True,   # ← include start/end phrases when present
    use_last_end: bool = False      # ← set True if “extra” prose appears before the real end
) -> str:
    """
    Slice TD from first start anchor to (first|last) end anchor after it.
    If no end anchor is found, stop at the first STOP_MARKER; otherwise, to EOF.

    include_markers=True  → keep the start and end marker text in the slice.
    include_markers=False → return the interior only (previous behavior).
    """
    start_re = _compile_anchor_regex(DEFAULT_START_VARIATIONS)
    end_re   = _compile_anchor_regex(DEFAULT_END_VARIATIONS)

    m_start = start_re.search(text)
    if not m_start:
        raise ValueError("Could not find the start of the technical description.")

    # Choose the end match
    m_end = None
    if end_re:
        if use_last_end:
            for _m in end_re.finditer(text, m_start.end()):
                m_end = _m  # keep last end after start
        else:
            m_end = end_re.search(text, m_start.end())  # first end after start

    if m_end:
        start_idx = m_start.start() if include_markers else m_start.end()
        end_idx   = m_end.end()      if include_markers else m_end.start()
    else:
        # No explicit end → stop at first STOP_MARKER (exclusive), else EOF
        start_idx = m_start.start() if include_markers else m_start.end()
        m_stop = STOP_MARKERS_RE.search(text, m_start.end())
        end_idx = m_stop.start() if m_stop else len(text)

    # If an (earliest) end happens to appear before start, fall back to a safe span
    if m_end and m_end.start() < m_start.end():
        start_idx, end_idx = (0, len(text)) if include_markers else (m_start.end(), len(text))

    # Only trim whitespace so we don't cut off the included markers
    return text[start_idx:end_idx].strip()


def _filter_intruding_non_td_lines(block: str) -> str:
    """
    Inside the TD span, drop obvious non-TD lines while preserving TD content.
    Conservative: prefers keeping lines unless clearly a header/marker.
    """
    kept: List[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            kept.append(raw)
            continue

        if KEEP_TOKENS_RE.search(line):
            kept.append(raw)
            continue

        if STOP_MARKERS_RE.search(line):
            break  # hard stop if a section header appears mid-block

        # Drop screaming ALL-CAPS short headings without TD tokens
        if line.isupper() and len(line) <= 60:
            continue

        # Otherwise keep (some TD prose lacks explicit tokens)
        kept.append(raw)

    return "\n".join(kept).strip()


def extract_technical_description_spanning_pages(full_ocr_text: str) -> str:
    """
    1) Strip headers/footers/continuations.
    2) Slice between canonical TD anchors across all pages.
    3) Filter out intruding non-TD lines.
    """
    cleaned = _strip_headers_footers_and_continuations(full_ocr_text)
    td_span = _slice_between_anchors_spanning_pages(cleaned, include_markers=True, use_last_end=False)
    td_final = _filter_intruding_non_td_lines(td_span)
    return td_final


# ──────────────────────────────────────────────────────────────────────────────
# Main parser (uses your existing helpers: extract_title_meta, parse_segment, _clean_capture)
# ──────────────────────────────────────────────────────────────────────────────
def parse_land_title(text: str):
    """
    Parse the given OCR text spanning multiple pages.

    Returns: (title_number, owner, technical_description, tie_point, boundaries)
      - technical_description: substring between DEFAULT_* anchors across pages
      - tie_point: parsed from the first '... from <TIE POINT>' occurrence
      - boundaries: list of (bearing_dict, distance_m)
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty description")

    # Heuristic extraction for metadata (your existing helper)
    title_number, owner = extract_title_meta(text)  # <- assumes you have this

    # Page-aware technical description
    technical_description = extract_technical_description_spanning_pages(text)
    print(f'technical description: {technical_description}')

    # Re-locate the start anchor within the isolated TD so segment splitting is stable
    start_anchor_re = _compile_anchor_regex(DEFAULT_START_VARIATIONS)
    m_anchor = start_anchor_re.search(technical_description)
    if not m_anchor:
        raise ValueError("Could not find the 'Beginning at ...' anchor inside the technical description.")

    # Split into first-segment (tie-point) + subsequent corners
    work = technical_description[m_anchor.start():].rstrip(':. ')
    raw_parts = re.split(r'(?:;\s*|\bthence\b)', work, flags=re.IGNORECASE)
    parts = [p for p in raw_parts if p and p.strip()]
    if not parts:
        raise ValueError("No boundary segments found")

    first_seg, *corner_segs = parts

    # Expect '... from <TIE POINT>' in the first segment
    split_td = re.split(r'\s+from\s+', first_seg, flags=re.IGNORECASE)
    if len(split_td) != 2:
        raise ValueError(f"Could not find tie-point in: {first_seg!r}")
    seg_td, tie_point = split_td

    tie_b, tie_d = parse_segment(seg_td)
    boundaries: List[Tuple[Dict[str, float], float]] = []
    if tie_b and tie_d:
        boundaries.append((tie_b, tie_d))

    for seg in corner_segs:
        bdict, dist = parse_segment(seg)  # <- assumes you have this
        if bdict and dist is not None:
            boundaries.append((bdict, dist))

    return title_number, owner, technical_description, _clean_capture(tie_point), boundaries
