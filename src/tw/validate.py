from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    missing: list[str]
    invalid: list[str]


def validate(output: dict, fields: list[str]) -> ValidationResult:
    missing = [f for f in fields if f not in output]
    invalid = [f for f in fields if f in output and not isinstance(output[f], str)]
    return ValidationResult(ok=not missing and not invalid, missing=missing, invalid=invalid)
