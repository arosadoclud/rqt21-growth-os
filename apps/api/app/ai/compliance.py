"""Content-safety heuristics for generated marketing copy.

These are pattern-based, not a full NLP claims-detector — good enough to
catch the obvious cases the business explicitly wants blocked, cheap to run,
and fully deterministic (required since tests must not depend on any model).
"""

from __future__ import annotations

import re

# Health/weight-loss/medical claim patterns we never want auto-approved.
# Case-insensitive, matched against the concatenation of all text fields.
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\bcura(r|s)?\b.*\b(enfermedad|diabetes|cancer|cáncer)\b", "unsubstantiated medical cure claim"),
    (r"\btratamiento (médico|para)\b", "presents product as a medical treatment"),
    (r"\bpierde[s]?\s+\d+\s*(kg|kilos|libras|lbs)\b", "extreme/guaranteed weight-loss claim"),
    (r"\bresultados?\s+garantizados?\b", "guaranteed-results claim"),
    (r"\b100%\s+garantizado\b", "guaranteed-results claim"),
    (r"\bsin\s+dietas?\s+ni\s+ejercicio\b", "unrealistic no-effort claim"),
    (r"\belimina(r)?\s+la\s+grasa\b", "extreme fat-elimination claim"),
    (r"\bmilagro(so|sa)?\b", "miracle-cure framing"),
    (r"\bdiagnóstico\b", "implies medical diagnosis capability"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _BLOCKED_PATTERNS]


def scan_compliance(text: str, forbidden_terms: list[str] | None = None) -> list[str]:
    """Return a list of human-readable blocking issues found in `text`.
    Empty list means no blocking violation was found."""
    issues: list[str] = []
    for pattern, label in _COMPILED:
        if pattern.search(text):
            issues.append(label)
    for term in forbidden_terms or []:
        term = term.strip()
        if term and term.lower() in text.lower():
            issues.append(f"uses forbidden term: {term}")
    return issues
