import re
from pathlib import Path

from docx import Document

_SPEAKER_TAG_RE = re.compile(r"\[(SPEAKER_\d+|UNKNOWN)\]")


def extract_speaker_labels(text: str) -> set[str]:
    return set(_SPEAKER_TAG_RE.findall(text))


def rename_speakers_in_text(text: str, mapping: dict[str, str]) -> str:
    return _SPEAKER_TAG_RE.sub(lambda m: f"[{mapping.get(m.group(1), m.group(1))}]", text)


def _docx_all_text(doc: Document) -> str:
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def extract_speakers_from_file(path: Path) -> set[str]:
    if path.suffix.lower() == ".docx":
        return extract_speaker_labels(_docx_all_text(Document(path)))
    return extract_speaker_labels(path.read_text())


def clean_speaker_name(name: str) -> str:
    """Normalize a user-supplied display name so it can't break the
    `[speaker]` tag format that previews and later renames parse."""
    return " ".join(name.replace("[", "").replace("]", "").split())


def rename_tags_in_text(text: str, mapping: dict[str, str]) -> str:
    """Rename `[name]` tags for arbitrary current names (e.g. "Mom" -> "Dad"),
    not just SPEAKER_nn labels. Substitution is simultaneous, so swaps work."""
    if not mapping:
        return text
    pattern = re.compile(r"\[(" + "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)) + r")\]")
    return pattern.sub(lambda m: f"[{mapping[m.group(1)]}]", text)


def _rename_paragraph(paragraph, mapping: dict[str, str], rename=rename_speakers_in_text) -> None:
    target = rename(paragraph.text, mapping)
    if target == paragraph.text:
        return
    # Prefer per-run replacement: keeps each run's formatting intact.
    for run in paragraph.runs:
        run.text = rename(run.text, mapping)
    if paragraph.text == target or not paragraph.runs:
        return
    # A tag was split across runs (Word does this after edits/spellcheck):
    # collapse the paragraph's text into its first run.
    paragraph.runs[0].text = target
    for run in paragraph.runs[1:]:
        run.text = ""


def rename_speakers_in_file(path: Path, mapping: dict[str, str], output_path: Path, rename=rename_speakers_in_text) -> Path:
    """`rename` is the text transform: SPEAKER_nn/UNKNOWN labels by default,
    or `rename_tags_in_text` to rename already-named speakers."""
    if path.suffix.lower() == ".docx":
        doc = Document(path)
        for p in doc.paragraphs:
            _rename_paragraph(p, mapping, rename)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Paragraph-level, not `cell.text = ...`, which would
                    # wipe the cell's paragraph/run formatting.
                    for p in cell.paragraphs:
                        _rename_paragraph(p, mapping, rename)
        doc.save(output_path)
        return output_path

    output_path.write_text(rename(path.read_text(), mapping))
    return output_path
