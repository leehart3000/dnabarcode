"""Add a known-answer check: a sequence and the answer it must keep giving.

Identifies the sequence with a local serving bundle and writes
``apps/dnabarcode/checks/<name>.json`` (the ``/identify`` request) and
``<name>.expected`` (the answer, or ``declined: <reason>``). Review the
printed answer before committing: the check freezes it, so any later change
in that answer stops a deploy until the check is updated on purpose.

Examples:
    pixi run python scripts/add_check.py aedes-aegypti-reverse \\
        --fasta ../prokoptonml_resources/fasta/Aedes_aegypti.fasta --reverse
    pixi run python scripts/add_check.py anopheles-gambiae-refseq \\
        --fasta apps/dnabarcode/reference/culicidae-refseq-cox1.fasta \\
        --match "Anopheles gambiae"
    pixi run python scripts/add_check.py declined-protein --text "MKLVEFIQ..."
"""

import argparse
import json
import sys
from pathlib import Path

from prokopton.ml.inference.bundle import load_bundle

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "apps/dnabarcode/checks"
COMPLEMENT = str.maketrans("ACGTRYKMBVDHNacgtrykmbvdhn", "TGCAYRMKVBHDNtgcayrmkvbhdn")


def read_record(path: Path, match: str | None) -> tuple[str, str]:
    """The first FASTA record (or the first whose header contains ``match``)."""
    header, lines, records = None, [], []
    for line in path.read_text("utf-8").splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(lines)))
            header, lines = line[1:].strip(), []
        elif line.strip():
            lines.append(line.strip())
    if header is not None:
        records.append((header, "".join(lines)))
    for header, sequence in records:
        if match is None or match in header:
            return header, sequence
    sys.exit(f"No record in {path} matches {match!r}")


def summary(result: dict[str, object]) -> str:
    """What a check compares: the answer text, or why it was declined."""
    answer = result.get("answer")
    if isinstance(answer, dict):
        return str(answer["text"])
    return f"declined: {result.get('reason')}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("name", help="File name for the check (letters, digits, -)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fasta", type=Path, help="Take a record from a FASTA file")
    source.add_argument("--text", help="Use this text as the submission, as it is")
    parser.add_argument("--match", help="With --fasta: header text to match")
    parser.add_argument("--reverse", action="store_true", help="Reverse complement it")
    parser.add_argument("--first", type=int, help="Keep only the first N bases")
    parser.add_argument(
        "--bundle", type=Path, default=ROOT / "data/models/dnabarcode/bundle"
    )
    parser.add_argument("--force", action="store_true", help="Replace a check")
    args = parser.parse_args()

    request_path = CHECKS / f"{args.name}.json"
    if request_path.exists() and not args.force:
        sys.exit(f"{request_path.name} exists; use --force to replace it")
    if args.text is not None:
        submission = args.text.replace("\\n", "\n")
    else:
        header, sequence = read_record(args.fasta, args.match)
        if args.reverse:
            sequence = sequence.translate(COMPLEMENT)[::-1]
            header += " (reverse complement)"
        if args.first:
            sequence = sequence[: args.first]
            header += f" (first {args.first} bases)"
        submission = f">{header}\n{sequence}"

    result = load_bundle(args.bundle).identifier.identify(submission)
    found = summary(json.loads(result.model_dump_json()))
    request_path.write_text(json.dumps({"sequence": submission}) + "\n", "utf-8")
    (CHECKS / f"{args.name}.expected").write_text(found + "\n", "utf-8")
    print(f"{args.name}: {found}")


if __name__ == "__main__":
    main()
