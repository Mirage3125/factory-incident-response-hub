PROMPT_VERSION = "stage3-v1"

SYSTEM_PROMPT = """
You analyze manufacturing incident records and return only valid JSON matching
the required schema. Do not invent credentials, workflow resume URLs, or hidden
system details. Provide recommendations only; deterministic backend rules decide
final severity and approval requirements.
""".strip()


def build_messages(payload: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this sanitized manufacturing incident:\n{payload}"},
    ]
