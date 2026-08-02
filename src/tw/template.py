import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_fields(template_path: Path) -> list[str]:
    text = template_path.read_text()
    fields = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            fields.append(match.group(2))
    return fields
