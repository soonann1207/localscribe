from typing import Callable

_VERDICTS = ("MISMATCH", "PARTIAL", "MATCH")  # MISMATCH checked first: "MATCH" is a substring of it


def build_judge_prompt(query: str, reference: str, extracted: str) -> str:
    return (
        "You are grading whether an extracted answer captures the same key "
        "information as a reference answer, for a meeting-notes query.\n\n"
        f"Query: {query}\n"
        f"Reference answer: {reference}\n"
        f"Extracted answer: {extracted}\n\n"
        "Respond with exactly one word: MATCH (captures the key information), "
        "PARTIAL (captures some but misses key details), or MISMATCH (wrong or unrelated)."
    )


def parse_verdict(raw: str) -> str:
    upper = raw.strip().upper()
    for verdict in _VERDICTS:
        if verdict in upper:
            return verdict
    return "MISMATCH"


def judge_match(query: str, reference: str, extracted: str, call_model: Callable[[str], str]) -> str:
    prompt = build_judge_prompt(query, reference, extracted)
    raw = call_model(prompt)
    return parse_verdict(raw)
