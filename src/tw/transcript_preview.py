"""Read a filled interval-transcript DOCX back into structured data.

Used by the web UI to preview a finished job's transcript without
downloading the document. Parsing the DOCX (rather than a separate
sidecar file) means the preview always matches what the user downloads,
including speaker renames and jobs produced before this module existed.
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from docx import Document

_INT_ROW_RE = re.compile(r"^Int (\d+)$")
# Turn format produced by tw.align.format_transcript: "[HH:MM:SS] [speaker] text"
_TURN_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] \[([^\]]+)\] ?(.*)$", re.DOTALL)


@dataclass
class Turn:
    timestamp: str
    speaker: str
    text: str


@dataclass
class Interval:
    label: str
    number: int | None
    turns: list[Turn]


def parse_turns(cell_text: str) -> list[Turn]:
    turns = []
    for block in re.split(r"\n\s*\n", cell_text.strip()):
        block = block.strip()
        if not block:
            continue
        match = _TURN_RE.match(block)
        if match:
            turns.append(Turn(timestamp=match.group(1), speaker=match.group(2), text=match.group(3).strip()))
        elif turns:
            turns[-1].text = f"{turns[-1].text}\n{block}".strip()  # continuation of the previous turn
        else:
            turns.append(Turn(timestamp="", speaker="", text=block))
    return turns


def read_interval_transcript(path: Path) -> list[Interval]:
    doc = Document(path)
    if not doc.tables:
        return []
    table = doc.tables[0]
    header = [c.text.strip() for c in table.rows[0].cells]
    if "Transcription" not in header:
        return []
    transcription_col = header.index("Transcription")

    intervals = []
    for row in table.rows[1:]:
        label = row.cells[0].text.strip()
        text = row.cells[transcription_col].text
        if not text.strip():
            continue
        match = _INT_ROW_RE.match(label)
        intervals.append(Interval(label=label, number=int(match.group(1)) if match else None, turns=parse_turns(text)))
    return intervals


def intervals_to_dicts(intervals: list[Interval]) -> list[dict]:
    return [asdict(i) for i in intervals]
