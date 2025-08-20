import re
from typing import Optional, Tuple, Dict

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
    deg = int(b["deg"]); mn = int(b["min"])
    sc = float(b["sec"]) if b.get("sec") else None
    ew = b["ew"].upper() if b.get("ew") else None
    post = seg_clean[m_b.end():]
    m_dist = re.search(r'(?P<dist>[\d\.]+)\s*m', post, flags=re.IGNORECASE)
    if not m_dist:
        raise ValueError(f"Could not parse distance in segment: {seg_clean!r}")
    dist = float(m_dist.group("dist"))
    return {"ns": ns, "degrees": deg, "minutes": mn, "seconds": sc, "ew": ew}, dist

def parse_land_title(desc: str):
    anchor_phrases = [r'beginning\s+at\s+a', r'beg.\s+at\s+a']
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
    tie_b, tie_d = parse_segment(seg_td)
    boundaries = [ (tie_b, tie_d) ]
    for seg in corner_segs:
        bdict, dist = parse_segment(seg)
        if bdict and dist:
            boundaries.append((bdict, dist))
    return tie_point.strip().rstrip(';'), boundaries
