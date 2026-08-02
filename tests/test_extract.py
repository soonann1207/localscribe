import json
from tw.extract import extract_fields, build_prompt


def test_build_prompt_includes_fields_and_transcript():
    prompt = build_prompt("SPEAKER_00: hello", ["Attendees", "Decisions"])
    assert "SPEAKER_00: hello" in prompt
    assert "Attendees" in prompt
    assert "Decisions" in prompt
    assert "Previous attempt" not in prompt


def test_build_prompt_includes_error_on_retry():
    prompt = build_prompt("transcript", ["Attendees"], error="missing fields: ['Attendees']")
    assert "Previous attempt was invalid" in prompt
    assert "missing fields: ['Attendees']" in prompt


def test_extract_fields_succeeds_first_try():
    def fake_call(prompt: str) -> str:
        return json.dumps({"Attendees": "Alice, Bob", "Decisions": "Ship v1"})

    result = extract_fields("transcript", ["Attendees", "Decisions"], fake_call)
    assert result.filled == {"Attendees": "Alice, Bob", "Decisions": "Ship v1"}
    assert result.failed_fields == []


def test_extract_fields_retries_then_succeeds():
    calls = []

    def fake_call(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps({"Attendees": "Alice"})  # missing Decisions
        return json.dumps({"Attendees": "Alice", "Decisions": "Ship v1"})

    result = extract_fields("transcript", ["Attendees", "Decisions"], fake_call)
    assert len(calls) == 2
    assert result.filled == {"Attendees": "Alice", "Decisions": "Ship v1"}
    assert result.failed_fields == []
    assert "missing fields" in calls[1]


def test_extract_fields_exhausts_retries_and_flags_field():
    def fake_call(prompt: str) -> str:
        return json.dumps({"Attendees": "Alice"})  # always missing Decisions

    result = extract_fields("transcript", ["Attendees", "Decisions"], fake_call)
    assert result.filled == {"Attendees": "Alice"}
    assert result.failed_fields == ["Decisions"]


def test_extract_fields_handles_invalid_json():
    def fake_call(prompt: str) -> str:
        return "not json"

    result = extract_fields("transcript", ["Attendees"], fake_call)
    assert result.failed_fields == ["Attendees"]
