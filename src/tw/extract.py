import json
from dataclasses import dataclass
from typing import Callable

from tw.validate import ValidationResult, validate

MAX_RETRIES = 2


@dataclass
class ExtractResult:
    filled: dict[str, str]
    failed_fields: list[str]


def build_prompt(labeled_transcript: str, fields: list[str], error: str | None = None) -> str:
    field_list = "\n".join(f"- {f}" for f in fields)
    prompt = (
        "You are extracting structured meeting notes from a transcript.\n\n"
        f"Transcript:\n{labeled_transcript}\n\n"
        f"Fields to fill:\n{field_list}\n\n"
        "Return a JSON object with exactly these field names as keys. "
        "If a field has no relevant content in the transcript, use the "
        "exact string \"Not mentioned in recording\" as its value."
    )
    if error:
        prompt += f"\n\nPrevious attempt was invalid: {error}\nFix and return the full JSON object again."
    return prompt


def extract_fields(
    labeled_transcript: str,
    fields: list[str],
    call_model: Callable[[str], str],
) -> ExtractResult:
    error: str | None = None
    output: dict = {}
    result = ValidationResult(ok=False, missing=list(fields), invalid=[])

    for _attempt in range(MAX_RETRIES + 1):
        prompt = build_prompt(labeled_transcript, fields, error)
        raw = call_model(prompt)
        try:
            output = json.loads(raw)
        except json.JSONDecodeError as e:
            error = f"response was not valid JSON: {e}"
            result = ValidationResult(ok=False, missing=list(fields), invalid=[])
            continue

        result = validate(output, fields)
        if result.ok:
            return ExtractResult(filled={f: output[f] for f in fields}, failed_fields=[])
        error = f"missing fields: {result.missing}, invalid fields: {result.invalid}"

    failed = result.missing + result.invalid
    filled = {f: output[f] for f in fields if f not in failed and f in output}
    return ExtractResult(filled=filled, failed_fields=failed)


def call_ollama(prompt: str, model: str = "llama3.3") -> str:
    import ollama

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    return response["message"]["content"]
