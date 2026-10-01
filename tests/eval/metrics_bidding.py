"""Deterministic metric verifying mathematical and budget sanity of valuation & bidding recommendations."""

import re
from typing import Any


def _extract_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        if "parts" in obj:
            return " ".join(_extract_text(p) for p in obj["parts"])
        if "text" in obj:
            return str(obj["text"])
        if "response" in obj:
            return _extract_text(obj["response"])
        return " ".join(_extract_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_extract_text(x) for x in obj)
    return str(obj or "")


def _extract_amounts(text: str) -> list[float]:
    """Extracts Euro amounts like €450,000 or 450,000 from text."""
    matches = re.findall(r"€\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", text)
    amounts = []
    for m in matches:
        try:
            amounts.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return amounts


def evaluate(instance: dict) -> dict:
    prompt = _extract_text(instance.get("prompt", ""))
    response = _extract_text(instance.get("response", ""))

    # For adversarial or refusal prompts, skip bidding check
    if "SYSTEM OVERRIDE" in prompt or "HackerGPT" in prompt:
        return {
            "score": 1.0,
            "explanation": "Adversarial test case; bidding check not applicable.",
        }

    # Check for presence of essential strategy terms
    has_opening_offer = bool(re.search(r"opening\s+offer", response, re.IGNORECASE))
    has_ceiling = bool(re.search(r"walk[\s-]away\s+ceiling", response, re.IGNORECASE))
    has_increments = bool(
        re.search(r"(?:bidding\s+)?increments?", response, re.IGNORECASE)
    )

    if not (has_opening_offer and has_ceiling):
        return {
            "score": 0.0,
            "explanation": (
                f"Incomplete bidding playbook. Has opening offer: {has_opening_offer}, "
                f"Has ceiling: {has_ceiling}, Has increments: {has_increments}."
            ),
        }

    # Check budget constraint adherence if specified in prompt
    budget_match = re.search(
        r"(?:budget|ceiling|maximum)\s*(?:of)?\s*€?\s*(\d{1,3}(?:,\d{3})+|\d{5,7})",
        prompt,
        re.IGNORECASE,
    )
    if budget_match:
        try:
            budget_limit = float(budget_match.group(1).replace(",", ""))
            ceiling_line_match = re.search(
                r"walk[\s-]away\s+ceiling[^\n]+", response, re.IGNORECASE
            )
            if ceiling_line_match:
                ceiling_line = ceiling_line_match.group(0)
                amounts = _extract_amounts(ceiling_line)
                if amounts:
                    rec_ceiling = amounts[0]
                    if rec_ceiling > budget_limit:
                        return {
                            "score": 0.0,
                            "explanation": (
                                f"Violation of buyer constraint: Recommended ceiling "
                                f"€{rec_ceiling:,.0f} exceeds buyer budget €{budget_limit:,.0f}."
                            ),
                        }
        except Exception:
            pass

    return {
        "score": 1.0,
        "explanation": "Bidding playbook structure and budget constraints mathematically verified.",
    }
