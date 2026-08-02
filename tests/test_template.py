from pathlib import Path
from tw.template import parse_fields

def test_parse_fields_from_headings(tmp_path):
    template = tmp_path / "template.md"
    template.write_text(
        "# Client Call Notes\n\n"
        "## Attendees\n\n"
        "## Decisions\n\n"
        "content placeholder\n\n"
        "## Follow-ups\n"
    )
    assert parse_fields(template) == ["Client Call Notes", "Attendees", "Decisions", "Follow-ups"]

def test_parse_fields_ignores_non_heading_hashes(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("## Notes\n\nUse #hashtags here, not a heading.\n")
    assert parse_fields(template) == ["Notes"]

def test_parse_fields_empty_for_no_headings(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("Just plain text, no ATX headings here.\n")
    assert parse_fields(template) == []
