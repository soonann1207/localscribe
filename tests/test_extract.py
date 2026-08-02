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


def test_extract_fields_preserves_early_success_despite_later_json_errors():
    """
    Bug fix: if an early attempt successfully extracts some fields but a later
    attempt fails to parse JSON, the successfully-extracted fields should be
    preserved in the final result, not discarded.
    """
    calls = []

    def fake_call(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            # First attempt: valid JSON with Attendees correct, Decisions invalid (non-string)
            return json.dumps({"Attendees": "Alice", "Decisions": 123})
        # Later attempts: malformed JSON (simulates Ollama failures)
        return "not valid json at all"

    result = extract_fields("transcript", ["Attendees", "Decisions"], fake_call)
    # Attendees was successfully extracted in attempt 0, despite later JSON parse failures
    assert result.filled == {"Attendees": "Alice"}
    assert result.failed_fields == ["Decisions"]


def test_extract_fields_recovers_from_early_json_error_to_late_success():
    """
    Verify that if an early attempt has invalid JSON but a later attempt
    succeeds, the extraction succeeds cleanly with a valid return.
    """
    calls = []

    def fake_call(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            # First attempt: malformed JSON
            return "definitely not json"
        # Second attempt: valid JSON with all fields correct
        return json.dumps({"Attendees": "Bob", "Decisions": "Postpone"})

    result = extract_fields("transcript", ["Attendees", "Decisions"], fake_call)
    assert len(calls) == 2
    assert result.filled == {"Attendees": "Bob", "Decisions": "Postpone"}
    assert result.failed_fields == []
