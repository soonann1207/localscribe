from docx import Document

from tw.transcript_preview import parse_turns, read_interval_transcript


def _make_docx(tmp_path, rows):
    doc = Document()
    table = doc.add_table(rows=1, cols=3)
    for cell, text in zip(table.rows[0].cells, ["Time", "Transcription", "Code"]):
        cell.text = text
    for label, transcription in rows:
        r = table.add_row()
        r.cells[0].text = label
        r.cells[1].text = transcription
    path = tmp_path / "out.docx"
    doc.save(path)
    return path


def test_parse_turns_splits_speaker_turns():
    turns = parse_turns("[00:00:01] [SPEAKER_00] hello there\n\n[00:00:05] [Mom] hi back")
    assert [(t.timestamp, t.speaker, t.text) for t in turns] == [
        ("00:00:01", "SPEAKER_00", "hello there"),
        ("00:00:05", "Mom", "hi back"),
    ]


def test_parse_turns_keeps_untagged_text():
    turns = parse_turns("some free text")
    assert turns[0].speaker == "" and turns[0].text == "some free text"


def test_read_interval_transcript_skips_empty_rows(tmp_path):
    path = _make_docx(
        tmp_path,
        [("Int 1", "[00:00:01] [SPEAKER_00] a"), ("Int 2", ""), ("Int 3", "[00:10:00] [SPEAKER_01] b")],
    )
    intervals = read_interval_transcript(path)
    assert [i.number for i in intervals] == [1, 3]
    assert intervals[1].turns[0].speaker == "SPEAKER_01"


def test_read_interval_transcript_without_table_returns_empty(tmp_path):
    doc = Document()
    doc.add_paragraph("nothing")
    path = tmp_path / "x.docx"
    doc.save(path)
    assert read_interval_transcript(path) == []
