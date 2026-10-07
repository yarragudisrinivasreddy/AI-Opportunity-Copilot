"""Redact obvious PII from free text before it is stored or sent to a model.

Covers emails, phone numbers, Aadhaar-style 12-digit numbers, PAN, and Luhn-valid card
numbers. This is a best-effort filter, not a guarantee; images use Cloud DLP (core/privacy.py).
"""
import re
from dataclasses import dataclass, field

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b")
_AADHAAR = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3,5}\)?[ -]?)?\d{3,5}[ -]?\d{4,5}(?!\d)")


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact_text(text: str) -> RedactionResult:
    counts: dict[str, int] = {}

    def sub(pattern: re.Pattern[str], label: str, source: str, check=None) -> str:
        def repl(match: re.Match[str]) -> str:
            if check and not check(match.group(0)):
                return match.group(0)
            counts[label] = counts.get(label, 0) + 1
            return f"[REDACTED_{label}]"

        return pattern.sub(repl, source)

    out = sub(_EMAIL, "EMAIL", text)
    out = sub(_PAN, "PAN", out)
    out = sub(
        _CARD,
        "CARD",
        out,
        check=lambda s: 13 <= len(re.sub(r"\D", "", s)) <= 19 and _luhn_ok(re.sub(r"\D", "", s)),
    )
    out = sub(_AADHAAR, "ID_NUMBER", out)
    out = sub(
        _PHONE, "PHONE", out, check=lambda s: 10 <= len(re.sub(r"\D", "", s)) <= 13
    )
    return RedactionResult(text=out, counts=counts)
