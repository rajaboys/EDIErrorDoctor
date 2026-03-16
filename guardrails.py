"""
guardrails.py — Lightweight PHI pattern detection before sending to Nova.
In production, replace with Amazon Bedrock Guardrails API.
"""
from __future__ import annotations
import re

# Patterns that suggest real PHI (not synthetic)
PHI_PATTERNS = [
    # SSN: 9 digits possibly hyphenated
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN pattern"),
    # MBI (Medicare): 11-char alphanumeric in specific format
    (r"\b[1-9][A-Z][A-Z0-9]\d[A-Z][A-Z0-9]\d[A-Z]{2}\d{2}\b", "MBI pattern"),
    # NPI-like 10-digit: less reliable, skip to avoid false positives
    # Real name heuristic: look for NM1 with very common real name patterns
    # (kept simple for demo — production uses Bedrock Guardrails)
]

# Synthetic sentinel — if file contains this marker, always pass
SYNTHETIC_MARKER = "SYNTHETIC"


def check_for_phi(edi_text: str) -> dict:
    """
    Returns {"detected": bool, "pattern": str}
    
    In production: call Amazon Bedrock Guardrails ApplyGuardrail API instead.
    Demo uses regex heuristics only.
    """
    upper = edi_text.upper()

    # Files explicitly marked synthetic always pass
    if SYNTHETIC_MARKER in upper:
        return {"detected": False, "pattern": None}

    for pattern, label in PHI_PATTERNS:
        if re.search(pattern, edi_text):
            return {"detected": True, "pattern": label}

    return {"detected": False, "pattern": None}
