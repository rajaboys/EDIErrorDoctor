"""
HL7 v2 Parser Utilities for EDIErrorDoctor
Handles HL7 v2.x message parsing, segment extraction, and pre-validation.
Supports ADT, ORU, ORM, and other common message types.
"""

import re
from typing import Optional


def detect_hl7_delimiters(hl7_text: str) -> dict:
    """Extract delimiters from MSH segment."""
    lines = hl7_text.strip().splitlines()
    for line in lines:
        if line.startswith("MSH"):
            field_sep = line[3]
            encoding_chars = line[4:8] if len(line) > 7 else "^~\\&"
            return {
                "field": field_sep,
                "component": encoding_chars[0] if len(encoding_chars) > 0 else "^",
                "repeat": encoding_chars[1] if len(encoding_chars) > 1 else "~",
                "escape": encoding_chars[2] if len(encoding_chars) > 2 else "\\",
                "subcomponent": encoding_chars[3] if len(encoding_chars) > 3 else "&",
            }
    return {"field": "|", "component": "^", "repeat": "~", "escape": "\\", "subcomponent": "&"}


def parse_hl7_segments(hl7_text: str) -> list[dict]:
    """Parse HL7 message into segments with fields."""
    delims = detect_hl7_delimiters(hl7_text)
    field_sep = delims["field"]

    segments = []
    for idx, line in enumerate(hl7_text.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        fields = line.split(field_sep)
        seg_id = fields[0]

        # MSH is special — field 1 IS the field separator
        if seg_id == "MSH":
            fields.insert(1, field_sep)

        segments.append({
            "index": idx,
            "id": seg_id,
            "fields": fields,
            "raw": line,
        })
    return segments


def detect_hl7_message_type(segments: list[dict]) -> str:
    """Identify HL7 message type from MSH-9."""
    for seg in segments:
        if seg["id"] == "MSH" and len(seg["fields"]) > 9:
            msg_type_field = seg["fields"][9]
            parts = msg_type_field.split("^")
            msg_type = parts[0].strip()
            trigger = parts[1].strip() if len(parts) > 1 else ""
            mapping = {
                "ADT": f"ADT - Admit/Discharge/Transfer ({trigger})",
                "ORU": f"ORU - Observation Result ({trigger})",
                "ORM": f"ORM - Order Message ({trigger})",
                "ORR": f"ORR - Order Response ({trigger})",
                "MDM": f"MDM - Medical Document Management ({trigger})",
                "SIU": f"SIU - Scheduling Information ({trigger})",
                "DFT": f"DFT - Detailed Financial Transaction ({trigger})",
                "BAR": f"BAR - Billing Account Record ({trigger})",
            }
            return mapping.get(msg_type, f"HL7 v2 {msg_type}^{trigger}")
    return "Unknown HL7 v2 Message"


def extract_hl7_errors(segments: list[dict], message_type: str) -> list[dict]:
    """
    Pre-validate HL7 v2 message for common errors.
    Returns list of flagged issues.
    """
    issues = []
    seg_ids = [s["id"] for s in segments]

    # MSH required
    if "MSH" not in seg_ids:
        issues.append({"snip": 1, "severity": "FATAL", "segment": "MSH",
                        "message": "Missing MSH segment — required header for all HL7 v2 messages."})
        return issues  # can't continue without MSH

    # Check MSH fields
    for seg in segments:
        if seg["id"] == "MSH":
            fields = seg["fields"]

            # MSH-3 Sending Application
            if len(fields) < 4 or not fields[3].strip():
                issues.append({"snip": 2, "severity": "ERROR", "segment": "MSH-3",
                                "message": "MSH-3 Sending Application is missing or empty."})

            # MSH-4 Sending Facility
            if len(fields) < 5 or not fields[4].strip():
                issues.append({"snip": 2, "severity": "ERROR", "segment": "MSH-4",
                                "message": "MSH-4 Sending Facility is missing or empty."})

            # MSH-7 Date/Time
            if len(fields) < 8 or not fields[7].strip():
                issues.append({"snip": 2, "severity": "ERROR", "segment": "MSH-7",
                                "message": "MSH-7 Message Date/Time is missing."})
            elif not re.match(r"^\d{8,14}", fields[7].strip()):
                issues.append({"snip": 2, "severity": "WARNING", "segment": "MSH-7",
                                "message": f"MSH-7 Date/Time '{fields[7]}' format appears invalid. Expected YYYYMMDDHHMMSS."})

            # MSH-9 Message Type
            if len(fields) < 10 or not fields[9].strip():
                issues.append({"snip": 2, "severity": "FATAL", "segment": "MSH-9",
                                "message": "MSH-9 Message Type is missing — cannot determine message structure."})

            # MSH-10 Message Control ID
            if len(fields) < 11 or not fields[10].strip():
                issues.append({"snip": 2, "severity": "ERROR", "segment": "MSH-10",
                                "message": "MSH-10 Message Control ID is missing — required for acknowledgment."})

            # MSH-12 Version ID
            if len(fields) < 13 or not fields[12].strip():
                issues.append({"snip": 2, "severity": "WARNING", "segment": "MSH-12",
                                "message": "MSH-12 Version ID is missing. Should be 2.3, 2.4, 2.5, 2.5.1, etc."})

    # PID checks for patient-level messages
    patient_messages = ["ADT", "ORU", "ORM", "DFT"]
    is_patient_msg = any(m in message_type for m in patient_messages)

    if is_patient_msg:
        if "PID" not in seg_ids:
            issues.append({"snip": 3, "severity": "FATAL", "segment": "PID",
                            "message": "PID segment missing — required for all patient-level HL7 messages."})
        else:
            for seg in segments:
                if seg["id"] == "PID":
                    fields = seg["fields"]

                    # PID-3 Patient ID
                    if len(fields) < 4 or not fields[3].strip():
                        issues.append({"snip": 3, "severity": "FATAL", "segment": "PID-3",
                                        "message": "PID-3 Patient Identifier List is empty — cannot identify patient."})

                    # PID-5 Patient Name
                    if len(fields) < 6 or not fields[5].strip():
                        issues.append({"snip": 3, "severity": "ERROR", "segment": "PID-5",
                                        "message": "PID-5 Patient Name is missing."})

                    # PID-7 Date of Birth
                    if len(fields) < 8 or not fields[7].strip():
                        issues.append({"snip": 3, "severity": "WARNING", "segment": "PID-7",
                                        "message": "PID-7 Date of Birth is missing."})
                    elif fields[7].strip() and not re.match(r"^\d{8}", fields[7].strip()):
                        issues.append({"snip": 3, "severity": "WARNING", "segment": "PID-7",
                                        "message": f"PID-7 DOB '{fields[7]}' format invalid. Expected YYYYMMDD."})

                    # PID-8 Sex
                    if len(fields) > 8 and fields[8].strip() not in ("M", "F", "O", "U", "A", "N", ""):
                        issues.append({"snip": 3, "severity": "WARNING", "segment": "PID-8",
                                        "message": f"PID-8 Administrative Sex '{fields[8]}' is not a valid HL7 code (M/F/O/U/A/N)."})

    # EVN segment for ADT
    if "ADT" in message_type and "EVN" not in seg_ids:
        issues.append({"snip": 3, "severity": "ERROR", "segment": "EVN",
                        "message": "EVN segment missing — required for ADT messages to indicate event type."})

    # OBR for ORU
    if "ORU" in message_type and "OBR" not in seg_ids:
        issues.append({"snip": 3, "severity": "ERROR", "segment": "OBR",
                        "message": "OBR segment missing — required for ORU observation results."})

    # OBX for ORU
    if "ORU" in message_type and "OBX" not in seg_ids:
        issues.append({"snip": 4, "severity": "WARNING", "segment": "OBX",
                        "message": "OBX segment missing — no observation values present in ORU message."})

    return issues


def summarize_hl7(segments: list[dict], message_type: str) -> str:
    """Generate a human-readable summary of the HL7 message."""
    counts = {}
    for seg in segments:
        counts[seg["id"]] = counts.get(seg["id"], 0) + 1

    return (
        f"**Message Type:** {message_type}\n"
        f"**Total Segments:** {len(segments)}\n"
        f"**Unique Segment Types:** {len(counts)}\n"
        f"**Segments Present:** {', '.join(sorted(counts.keys()))}"
    )


def is_hl7_message(text: str) -> bool:
    """Detect if the input is an HL7 v2 message."""
    stripped = text.strip()
    return stripped.startswith("MSH|") or stripped.startswith("MSH^")
