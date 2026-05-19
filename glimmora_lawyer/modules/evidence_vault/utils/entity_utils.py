"""Entity normalization helpers — shared between Gemini path and fallback."""
from __future__ import annotations

import calendar
import re
from typing import Optional


_MONTH_TO_NUM = {m.lower()[:3]: i for i, m in enumerate(calendar.month_name) if m}
_MONTH_TO_NUM.update({"sept": 9})


def normalize_value(entity_type: str, raw: str) -> str:
    """Best-effort canonical form per entity type. Falls back to trimmed raw."""
    raw = (raw or "").strip()
    if not raw:
        return raw
    et = entity_type.upper()

    if et == "DATE":
        iso = _try_iso_date(raw)
        if iso:
            return iso
    if et == "AMOUNT":
        num = _try_numeric_amount(raw)
        if num is not None:
            return num
    if et in {"ACT", "LAW"}:
        return _canonical_act(raw)
    if et in {"PERSON", "WITNESS"}:
        return _canonical_person(raw)
    if et == "ORG":
        return _canonical_org(raw)
    if et == "SECTION":
        return _canonical_section(raw)
    if et == "CLAUSE":
        return _canonical_clause(raw)
    if et == "RULE":
        return _canonical_rule(raw)
    if et == "CASE_NUMBER":
        return re.sub(r"\s+", " ", raw).strip()
    return raw


# ---- Date ----

_NUMERIC = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_TEXT_DM = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\.?\s+(\d{4})\b"
)
_TEXT_MD = re.compile(
    r"\b([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})\b"
)


def _try_iso_date(raw: str) -> Optional[str]:
    if m := _NUMERIC.search(raw):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 50 else 1900
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    if m := _TEXT_DM.search(raw):
        d = int(m.group(1))
        mo = _MONTH_TO_NUM.get(m.group(2).lower()[:3], 0)
        y = int(m.group(3))
        if mo and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    if m := _TEXT_MD.search(raw):
        mo = _MONTH_TO_NUM.get(m.group(1).lower()[:3], 0)
        d = int(m.group(2))
        y = int(m.group(3))
        if mo and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


# ---- Amount ----

def _try_numeric_amount(raw: str) -> Optional[str]:
    """Returns a string of the canonical numeric value, e.g. 'INR 12400000' for
    'Rs. 12,40,00,000'. Handles crore/lakh suffixes."""
    txt = raw.replace(",", " ").strip()
    # Detect currency prefix
    currency = "INR"
    if "₹" in raw or re.search(r"\b(?:Rs|INR)\.?", raw, re.I):
        currency = "INR"
    # Detect units
    multiplier = 1
    low = raw.lower()
    if "crore" in low:
        multiplier = 10_000_000
    elif "lakh" in low:
        multiplier = 100_000
    elif "million" in low:
        multiplier = 1_000_000
    elif "thousand" in low:
        multiplier = 1_000
    # Extract numeric part
    nums = re.findall(r"\d+(?:\.\d+)?", txt)
    if not nums:
        return None
    try:
        # Indian-style: combine digit groups left-to-right
        if multiplier > 1 and len(nums) == 1:
            value = float(nums[0]) * multiplier
        else:
            value = float("".join(nums))
        if value == int(value):
            return f"{currency} {int(value)}"
        return f"{currency} {value:.2f}"
    except ValueError:
        return None


# ---- Acts / Laws ----

def _canonical_act(raw: str) -> str:
    out = re.sub(r"\s+", " ", raw).strip().strip(",")
    # Normalise "Indian Contract Act 1872" / "Indian Contract Act, 1872"
    m = re.search(r"(.*?Act)[\s,]+(\d{4})", out, re.I)
    if m:
        return f"{m.group(1).strip()}, {m.group(2)}"
    return out


def _canonical_section(raw: str) -> str:
    m = re.search(r"(?:Section|Sec\.?|s\.)\s*(\d+[A-Za-z]*(?:\(\d+\))?)",
                  raw, re.I)
    return f"Section {m.group(1)}" if m else raw.strip()


def _canonical_clause(raw: str) -> str:
    m = re.search(r"[Cc]lause\s+(\d+(?:\.\d+)*)", raw)
    return f"Clause {m.group(1)}" if m else raw.strip()


def _canonical_rule(raw: str) -> str:
    m = re.search(r"[Rr]ule\s+(\d+(?:\([0-9A-Za-z]+\))?)", raw)
    return f"Rule {m.group(1)}" if m else raw.strip()


def _canonical_person(raw: str) -> str:
    out = re.sub(r"\b(Mr|Mrs|Ms|Miss|Dr|Shri|Smt|Sri)\.?\s+", "", raw,
                 flags=re.I).strip()
    return re.sub(r"\s+", " ", out)


def _canonical_org(raw: str) -> str:
    out = re.sub(r"\s+", " ", raw).strip().rstrip(".,;")
    return out
