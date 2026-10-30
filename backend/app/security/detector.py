
import re


SUSPICIOUS_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all previous rules",
    r"reveal confidential information",
    r"send .* (files|data|documents)",
    r"bypass security",
    r"override system instructions",
    r"disregard your instructions",
    r"reveal secrets"
]


def detect_prompt_injection(content: str):

    if not content:
        return {
            "is_suspicious": False,
            "reason": "No content to inspect."
        }

    for pattern in SUSPICIOUS_PATTERNS:

        if re.search(pattern, content, re.IGNORECASE):

            return {
                "is_suspicious": True,
                "reason": f"Suspicious instruction detected: {pattern}"
            }

    return {
        "is_suspicious": False,
        "reason": "No known suspicious pattern detected."
    }
