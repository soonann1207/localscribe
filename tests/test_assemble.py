import pytest
from tw.assemble import assemble


def test_assemble_fills_all_fields(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("## Attendees\n\n## Decisions\n")
    result = assemble(template, {"Attendees": "Alice, Bob", "Decisions": "Ship v1"}, [])
    assert "## Attendees\n\nAlice, Bob" in result
    assert "## Decisions\n\nShip v1" in result
    assert "NEEDS MANUAL REVIEW" not in result


def test_assemble_marks_failed_fields(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("## Attendees\n\n## Decisions\n")
    result = assemble(template, {"Attendees": "Alice, Bob"}, ["Decisions"])
    assert "## Decisions\n\n[NEEDS MANUAL REVIEW]" in result
    assert "> **NEEDS MANUAL REVIEW:** Decisions" in result


def test_assemble_preserves_preamble(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("# Client Call Notes\n\n## Attendees\n")
    result = assemble(template, {"Client Call Notes": "", "Attendees": "Alice"}, [])
    assert result.startswith("# Client Call Notes")


def test_assemble_raises_on_unaccounted_field(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("## Attendees\n\n## Decisions\n")
    with pytest.raises(ValueError, match="Decisions"):
        assemble(template, {"Attendees": "Alice"}, [])


def test_assemble_multiple_failed_fields(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("## Attendees\n\n## Decisions\n\n## Action Items\n")
    result = assemble(
        template,
        {"Attendees": "Alice"},
        ["Decisions", "Action Items"]
    )
    assert "> **NEEDS MANUAL REVIEW:** Decisions, Action Items" in result
    assert "## Decisions\n\n[NEEDS MANUAL REVIEW]" in result
    assert "## Action Items\n\n[NEEDS MANUAL REVIEW]" in result
