import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def assemble(template_path: Path, filled: dict[str, str], failed_fields: list[str]) -> str:
    lines = template_path.read_text().splitlines()

    headings = []
    for i, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((i, line, match.group(2)))

    parts = []
    if failed_fields:
        parts.append("> **NEEDS MANUAL REVIEW:** " + ", ".join(failed_fields))

    for i, (line_no, heading_line, field_name) in enumerate(headings):
        if field_name in failed_fields:
            content = "[NEEDS MANUAL REVIEW]"
        else:
            content = filled.get(field_name, "[NEEDS MANUAL REVIEW]")
        parts.append(f"{heading_line}\n\n{content}".rstrip())

    return "\n\n".join(parts) + "\n"
