import pytest
from docx import Document

from tw.doc_edit import CellEdit, apply_cell_edits, read_table


def _doc(tmp_path):
    doc = Document()
    table = doc.add_table(rows=3, cols=3)
    for i, h in enumerate(["Time", "Transcription", "Code"]):
        table.rows[0].cells[i].text = h
    table.rows[1].cells[0].text = "Int 1"
    run = table.rows[1].cells[1].paragraphs[0].add_run("[00:00:01] [SPEAKER_00] helo")
    run.bold = True
    table.rows[2].cells[0].text = "Int 2"
    path = tmp_path / "doc.docx"
    doc.save(path)
    return path


def test_read_table(tmp_path):
    t = read_table(_doc(tmp_path))
    assert t["header"] == ["Time", "Transcription", "Code"]
    assert t["rows"][0][:2] == ["Int 1", "[00:00:01] [SPEAKER_00] helo"]


def test_apply_edits_keeps_formatting_and_line_breaks(tmp_path):
    path = _doc(tmp_path)
    out = tmp_path / "out.docx"
    apply_cell_edits(
        path,
        [CellEdit(1, 1, "[00:00:01] [SPEAKER_00] hello\n\n[00:00:09] [SPEAKER_01] hi"), CellEdit(1, 2, "Q1")],
        out,
    )
    cell = Document(out).tables[0].rows[1].cells[1]
    assert cell.text == "[00:00:01] [SPEAKER_00] hello\n\n[00:00:09] [SPEAKER_01] hi"
    assert len(cell.paragraphs) == 1
    assert cell.paragraphs[0].runs[0].bold is True
    assert Document(out).tables[0].rows[1].cells[2].text == "Q1"


def test_header_and_out_of_range_edits_rejected(tmp_path):
    path = _doc(tmp_path)
    with pytest.raises(ValueError):
        apply_cell_edits(path, [CellEdit(0, 0, "x")], tmp_path / "o.docx")
    with pytest.raises(ValueError):
        apply_cell_edits(path, [CellEdit(1, 9, "x")], tmp_path / "o.docx")
