"""Read and edit the cells of a filled interval-transcript DOCX.

Backs the web UI's "Edit" mode: users fix transcription errors and fill the
Code / Misc. columns in the browser, and the edits are written back into the
document while keeping its table, paragraph and run formatting.
"""

import copy
from dataclasses import dataclass
from pathlib import Path

from docx import Document


@dataclass
class CellEdit:
    row: int  # absolute table row index; 0 is the header and is read-only
    col: int
    text: str


def read_table(path: Path) -> dict:
    doc = Document(path)
    if not doc.tables:
        return {"header": [], "rows": []}
    table = doc.tables[0]
    header = [c.text for c in table.rows[0].cells]
    rows = [[c.text for c in row.cells] for row in table.rows[1:]]
    return {"header": header, "rows": rows}


def set_cell_text(cell, text: str) -> None:
    """Replace a cell's text, keeping the formatting of its first paragraph
    and first run. Newlines become line breaks inside one paragraph, the
    same representation the pipeline writes (python-docx `cell.text = ...`)."""
    paragraphs = cell.paragraphs
    first = paragraphs[0]
    for extra in paragraphs[1:]:
        extra._element.getparent().remove(extra._element)

    run_props = None
    if first.runs and first.runs[0]._element.rPr is not None:
        run_props = copy.deepcopy(first.runs[0]._element.rPr)
    for run in list(first.runs):
        run._element.getparent().remove(run._element)

    new_run = first.add_run(text)  # python-docx maps \n -> <w:br/>, \t -> <w:tab/>
    if run_props is not None:
        new_run._element.insert(0, run_props)


def apply_cell_edits(path: Path, edits: list[CellEdit], output_path: Path) -> Path:
    doc = Document(path)
    if not doc.tables:
        raise ValueError("document has no table to edit")
    table = doc.tables[0]
    n_rows, n_cols = len(table.rows), len(table.columns)
    for edit in edits:
        if not (1 <= edit.row < n_rows) or not (0 <= edit.col < n_cols):
            raise ValueError(f"cell ({edit.row}, {edit.col}) is outside the editable table")
    for edit in edits:
        cell = table.rows[edit.row].cells[edit.col]
        if cell.text != edit.text:
            set_cell_text(cell, edit.text)
    doc.save(output_path)
    return output_path
