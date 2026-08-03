from tw.judge import build_judge_prompt, judge_match, parse_verdict


def test_build_judge_prompt_includes_query_reference_and_extracted():
    prompt = build_judge_prompt("What did the team decide?", "Ship v1 next week", "They decided to ship v1")
    assert "What did the team decide?" in prompt
    assert "Ship v1 next week" in prompt
    assert "They decided to ship v1" in prompt


def test_parse_verdict_extracts_match():
    assert parse_verdict("MATCH") == "MATCH"
    assert parse_verdict("  match\n") == "MATCH"


def test_parse_verdict_extracts_partial():
    assert parse_verdict("PARTIAL") == "PARTIAL"


def test_parse_verdict_extracts_mismatch():
    assert parse_verdict("MISMATCH") == "MISMATCH"


def test_parse_verdict_defaults_to_mismatch_when_unparseable():
    assert parse_verdict("I'm not sure what to say here") == "MISMATCH"


def test_judge_match_calls_model_and_parses_verdict():
    def fake_call(prompt: str) -> str:
        assert "query" in prompt.lower() or "What" in prompt
        return "MATCH"

    result = judge_match("What?", "reference answer", "extracted answer", fake_call)
    assert result == "MATCH"
