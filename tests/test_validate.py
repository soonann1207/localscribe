from tw.validate import validate


def test_validate_ok_when_all_fields_present_as_strings():
    result = validate({"Attendees": "Alice, Bob", "Decisions": "Ship v1"}, ["Attendees", "Decisions"])
    assert result.ok is True
    assert result.missing == []
    assert result.invalid == []


def test_validate_reports_missing_fields():
    result = validate({"Attendees": "Alice"}, ["Attendees", "Decisions"])
    assert result.ok is False
    assert result.missing == ["Decisions"]
    assert result.invalid == []


def test_validate_reports_invalid_non_string_fields():
    result = validate({"Attendees": "Alice", "Decisions": ["Ship v1"]}, ["Attendees", "Decisions"])
    assert result.ok is False
    assert result.missing == []
    assert result.invalid == ["Decisions"]


def test_validate_reports_blank_string_as_invalid():
    result = validate({"Attendees": "   "}, ["Attendees"])
    assert result.ok is False
    assert result.invalid == ["Attendees"]
