"""
EDI Parser Utilities for EDIErrorDoctor
Handles X12 segment/loop extraction and preprocessing for Nova analysis.
"""

import re
from typing import Optional


def detect_delimiters(edi_text: str) -> dict:
    """Extract ISA-defined delimiters from the EDI envelope."""
    edi_text = edi_text.strip()
    if not edi_text.startswith("ISA"):
        return {"element": "*", "sub_element": ":", "segment": "~"}

    # Element separator is always position 3
    element_sep = edi_text[3]

    # Split ISA by element separator to get all fields
    # ISA has exactly 16 elements - segment terminator follows ISA16
    isa_elements = edi_text[:200].split(element_sep)

    if len(isa_elements) >= 17:
        # ISA16 is the component separator, segment terminator is right after
        isa16 = isa_elements[16]
        # Segment terminator is the first char of ISA16 field remainder
        seg_sep = isa16[1] if len(isa16) > 1 else isa16[0]
        sub_sep = isa16[0]
    else:
        sub_sep = ":"
        seg_sep = "~"

    return {
        "element": element_sep,
        "sub_element": sub_sep,
        "segment": seg_sep
    }


def parse_segments(edi_text: str) -> list[dict]:
    """Split EDI into individual segments with metadata."""
    # Remove ALL whitespace between segments but preserve content
    edi_text = edi_text.strip()
    delims = detect_delimiters(edi_text)
    seg_sep = delims["segment"]
    elem_sep = delims["element"]

    # Remove newlines and carriage returns AFTER splitting on segment terminator
    raw_segments = [
        s.strip().replace("\n", "").replace("\r", "")
        for s in edi_text.split(seg_sep)
        if s.strip()
    ]

    segments = []
    for idx, raw in enumerate(raw_segments):
        if not raw:
            continue
        elements = raw.split(elem_sep)
        segments.append({
            "index": idx,
            "id": elements[0].strip() if elements else "",
            "elements": elements,
            "raw": raw + seg_sep,
        })
    return segments


def detect_transaction_type(segments: list[dict]) -> str:
    """Identify the X12 transaction set type."""
    # First try ST segment
    for seg in segments:
        if seg["id"] == "ST" and len(seg["elements"]) > 1:
            ts_id = seg["elements"][1]
            mapping = {
                "837": "837 Health Care Claim",
                "835": "835 Electronic Remittance Advice",
                "278": "278 Prior Authorization",
                "270": "270 Eligibility Inquiry",
                "271": "271 Eligibility Response",
                "276": "276 Claim Status Request",
                "277": "277 Claim Status Response",
            }
            return mapping.get(ts_id, f"X12 {ts_id}")

    # Fallback: guess from GS segment (GS01 functional identifier)
    for seg in segments:
        if seg["id"] == "GS" and len(seg["elements"]) > 1:
            gs01 = seg["elements"][1]
            gs_mapping = {
                "HC": "837 Health Care Claim",
                "HP": "835 Electronic Remittance Advice",
                "HI": "278 Prior Authorization",
                "HS": "270 Eligibility Inquiry",
                "HB": "271 Eligibility Response",
                "HR": "276 Claim Status Request",
                "HN": "277 Claim Status Response",
            }
            if gs01 in gs_mapping:
                return gs_mapping[gs01] + " (detected from GS)"

    # Fallback: guess from segment presence
    seg_ids = [s["id"] for s in segments]
    if "CLM" in seg_ids:
        return "837 Health Care Claim (inferred)"
    if "CLP" in seg_ids:
        return "835 Electronic Remittance Advice (inferred)"
    if "UM" in seg_ids:
        return "278 Prior Authorization (inferred)"
    if "EQ" in seg_ids:
        return "270 Eligibility Inquiry (inferred)"

    return "Unknown X12 Transaction"

def extract_snip_errors(segments: list[dict], transaction_type: str) -> list[dict]:
    """
    Perform lightweight pre-validation to flag obvious structural errors
    before sending to Nova. Returns a list of flagged issues.
    """
    issues = []
    seg_ids = [s["id"] for s in segments]

    # SNIP Level 1: ISA/GS/ST envelope checks
    if "ISA" not in seg_ids:
        issues.append({"snip": 1, "severity": "FATAL", "segment": "ISA",
                        "message": "Missing ISA envelope header."})
    if "IEA" not in seg_ids:
        issues.append({"snip": 1, "severity": "FATAL", "segment": "IEA",
                        "message": "Missing IEA envelope trailer."})
    if "GS" not in seg_ids:
        issues.append({"snip": 1, "severity": "ERROR", "segment": "GS",
                        "message": "Missing GS functional group header."})
    if "ST" not in seg_ids:
        issues.append({"snip": 1, "severity": "FATAL", "segment": "ST",
                        "message": "Missing ST transaction set header."})

    # SNIP Level 2: Required segment presence
    if "837" in transaction_type:
        required = ["BHT", "NM1", "CLM", "SV1"]
        for req in required:
            if req not in seg_ids:
                issues.append({"snip": 2, "severity": "ERROR", "segment": req,
                                "message": f"Required segment {req} missing for 837 claim."})

    # Check ISA length (must be exactly 106 chars before segment terminator)
    for seg in segments:
        if seg["id"] == "ISA":
            isa_raw = seg["raw"].rstrip("~").rstrip()
            if len(isa_raw) != 106:
                issues.append({
                    "snip": 1, "severity": "ERROR", "segment": "ISA",
                    "message": f"ISA segment length is {len(isa_raw)}, expected 106. Fixed-width violation."
                })

    # N4 zip code check (basic)
    for seg in segments:
        if seg["id"] == "N4" and len(seg["elements"]) >= 4:
            zip_code = seg["elements"][3]
            if zip_code and not re.match(r"^\d{5}(-\d{4})?$", zip_code):
                issues.append({
                    "snip": 3, "severity": "WARNING", "segment": "N4",
                    "message": f"Postal code '{zip_code}' appears malformed (expected 5 or 9 digits)."
                })

    # DMG gender code check
    for seg in segments:
        if seg["id"] == "DMG" and len(seg["elements"]) >= 4:
            gender = seg["elements"][3]
            if gender and gender not in ("M", "F", "U"):
                issues.append({
                    "snip": 4, "severity": "ERROR", "segment": "DMG",
                    "message": f"DMG03 gender code '{gender}' invalid. Must be M, F, or U."
                })

    return issues


def chunk_edi_for_context(segments: list[dict], max_segments: int = 80) -> list[list[dict]]:
    """Split large EDI files into chunks for context window management."""
    return [segments[i:i + max_segments] for i in range(0, len(segments), max_segments)]


def segments_to_text(segments: list[dict]) -> str:
    """Reconstruct EDI text from parsed segments."""
    return "\n".join(s["raw"] for s in segments)


def summarize_edi(segments: list[dict], transaction_type: str) -> str:
    """Generate a human-readable summary for display."""
    counts = {}
    for seg in segments:
        counts[seg["id"]] = counts.get(seg["id"], 0) + 1

    clm_count = counts.get("CLM", 0)
    nm1_count = counts.get("NM1", 0)
    total = len(segments)

    return (
        f"**Transaction Type:** {transaction_type}\n"
        f"**Total Segments:** {total}\n"
        f"**Claim Loops (CLM):** {clm_count}\n"
        f"**Name Segments (NM1):** {nm1_count}\n"
        f"**Unique Segment Types:** {len(counts)}"
    )
