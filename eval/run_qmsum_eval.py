"""Extraction-only eval harness: feeds QMSum meeting transcripts straight
into extract_fields() (skipping audio/diarization) and scores the result
against QMSum's reference answers via LLM-judge.

Usage:
    uv run python eval/run_qmsum_eval.py --data-dir samples/QMSum/data/Academic/test --limit 5
"""

import argparse
import json
from pathlib import Path

from tw.extract import call_ollama, extract_fields
from tw.judge import judge_match


def load_examples(data_dir: Path, limit: int) -> list[dict]:
    files = sorted(data_dir.glob("*.json"))[:limit]
    examples = []
    for f in files:
        data = json.loads(f.read_text())
        transcript = "\n\n".join(f"[{t['speaker']}] {t['content']}" for t in data["meeting_transcripts"])
        queries = {q["query"]: q["answer"] for q in data["specific_query_list"]}
        examples.append({"file": f.name, "transcript": transcript, "queries": queries})
    return examples


def run_eval(data_dir: Path, limit: int, details_path: Path | None) -> None:
    examples = load_examples(data_dir, limit)
    total, matched, partial, mismatched = 0, 0, 0, 0
    details = []

    for example in examples:
        fields = list(example["queries"].keys())
        result = extract_fields(example["transcript"], fields, call_model=call_ollama)

        print(f"\n=== {example['file']} ({len(fields)} fields) ===")
        for field in fields:
            extracted = result.filled.get(field, "[NOT EXTRACTED]")
            reference = example["queries"][field]
            verdict = judge_match(field, reference, extracted, call_ollama)

            total += 1
            if verdict == "MATCH":
                matched += 1
            elif verdict == "PARTIAL":
                partial += 1
            else:
                mismatched += 1

            print(f"  [{verdict}] {field[:60]}")
            details.append(
                {
                    "file": example["file"],
                    "query": field,
                    "reference": reference,
                    "extracted": extracted,
                    "verdict": verdict,
                }
            )

    print(f"\n=== Summary: {total} fields evaluated ===")
    print(f"MATCH: {matched} ({matched / total:.0%})")
    print(f"PARTIAL: {partial} ({partial / total:.0%})")
    print(f"MISMATCH: {mismatched} ({mismatched / total:.0%})")

    if details_path:
        details_path.write_text(json.dumps(details, indent=2))
        print(f"\nPer-field details written to {details_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("samples/QMSum/data/Academic/test"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--save-details", type=Path, default=None)
    args = parser.parse_args()
    run_eval(args.data_dir, args.limit, args.save_details)
