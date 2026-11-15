"""The golden set: about 200 sequences whose full answers must not change.

While the platform is reorganised, every DNAbarcode.org answer must stay
exactly the same. The known-answer checks compare only the answer text of 13
sequences; the golden set compares everything (answer, notes, strand, region
and the decision trace, but not timings) for about 200 sequences from the
test splits, chosen to cover each kind of answer.

    pixi run python scripts/golden.py select          # choose the sequences (once)
    pixi run python scripts/golden.py write           # record the answers
    pixi run python scripts/golden.py check           # compare a bundle's answers
    pixi run python scripts/golden.py check --bundle PATH

``select`` and ``write`` refuse to replace existing files without
``--force``: the point of the set is that it stays the same. After a
deliberate change (new models or references), run ``check`` to see every
difference, review them, then ``write --force``.
"""

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from prokopton.ml.inference.bundle import load_bundle

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "apps/dnabarcode/golden"
SEQUENCES = GOLDEN / "sequences.jsonl"
ANSWERS = GOLDEN / "answers.jsonl"
SPLITS = ROOT / "data/splits/dnabarcode/midori2_gb273"
BUNDLE = ROOT / "data/models/dnabarcode/bundle"
SALT = "dnabarcode-golden-v1"
COMPLEMENT = str.maketrans("ACGTRYKMBVDHNacgtrykmbvdhn", "TGCAYRMKVBHDNtgcayrmkvbhdn")
COLUMNS = ["record_id", "species", "species_named", "family", "order", "length"]
TEST = [("split", "in", ["test_known", "test_novel"])]

Record = dict[str, Any]


def _rank(record_id: str) -> str:
    return hashlib.sha256(f"{SALT}:{record_id}".encode()).hexdigest()


def _path(gene: str) -> Path:
    path = SPLITS / f"gene={gene}" / "records.parquet"
    if not path.exists():
        sys.exit(f"Missing {path}: run the pipeline's split stage first")
    return path


def _records(gene: str) -> list[Record]:
    """The gene's test records (without sequences, to save memory), in a fixed
    order that looks random."""
    table = pq.read_table(_path(gene), columns=[*COLUMNS, "split"], filters=TEST)
    records = table.to_pylist()
    records.sort(key=lambda r: _rank(r["record_id"]))
    return records


def _add_sequences(gene: str, records: list[Record]) -> list[Record]:
    """Read the sequences of the chosen records."""
    wanted = [r["record_id"] for r in records]
    table = pq.read_table(
        _path(gene),
        columns=["record_id", "sequence"],
        filters=[("record_id", "in", wanted)],
    )
    sequences = {row["record_id"]: row["sequence"] for row in table.to_pylist()}
    return [{**r, "sequence": sequences[r["record_id"]]} for r in records]


def _pick(
    records: list[Record], count: int, key: str, taken: set[str], test: Any
) -> list[Record]:
    """Up to ``count`` records passing ``test``, at most one per ``key``."""
    chosen, seen = [], set()
    for record in records:
        if len(chosen) == count:
            break
        group = record[key] or record["record_id"]
        if record["record_id"] in taken or group in seen or not test(record):
            continue
        seen.add(group)
        taken.add(record["record_id"])
        chosen.append(record)
    if len(chosen) < count:
        print(f"Note: only {len(chosen)} of {count} found", file=sys.stderr)
    return chosen


def _entry(stratum: str, record: Record, sequence: str, note: str = "") -> Record:
    header = f"{record['record_id']} {record['species'] or ''}{note}".strip()
    return {
        "id": f"{stratum}-{record['record_id']}",
        "stratum": stratum,
        "record_id": record["record_id"],
        "species": record["species"],
        "sequence": f">{header}\n{sequence}",
    }


def select(force: bool) -> None:
    if SEQUENCES.exists() and not force:
        sys.exit(f"{SEQUENCES.name} exists; use --force to choose again")
    genes = sorted(p.name.removeprefix("gene=") for p in SPLITS.glob("gene=*"))
    if "CO1" not in genes:
        sys.exit(f"No CO1 split in {SPLITS}")
    co1 = _records("CO1")
    taken: set[str] = set()

    def culicidae(r: Record) -> bool:
        return r["family"] == "Culicidae"

    def known(r: Record) -> bool:
        return r["split"] == "test_known"

    entries: list[Record] = []
    plan = [
        (
            "mosquito",
            50,
            "species",
            lambda r: culicidae(r) and known(r) and r["species_named"],
        ),
        (
            "mosquito-novel",
            25,
            "species",
            lambda r: culicidae(r) and r["split"] == "test_novel",
        ),
        (
            "mosquito-unnamed",
            10,
            "species",
            lambda r: culicidae(r) and known(r) and not r["species_named"],
        ),
        (
            "other-fly",
            25,
            "family",
            lambda r: r["order"] == "Diptera" and not culicidae(r) and known(r),
        ),
        ("other-animal", 40, "order", lambda r: r["order"] != "Diptera" and known(r)),
    ]
    for stratum, count, key, test in plan:
        entries += [
            _entry(stratum, r, r["sequence"])
            for r in _add_sequences("CO1", _pick(co1, count, key, taken, test))
        ]

    # Fragments and the other strand of mosquito sequences
    extra = _pick(
        co1,
        18,
        "species",
        taken,
        lambda r: (
            culicidae(r) and known(r) and r["species_named"] and r["length"] >= 600
        ),
    )
    extra = _add_sequences("CO1", extra)
    chance = random.Random(SALT)
    for number, record in enumerate(extra):
        sequence = record["sequence"]
        if number < 6:
            entries.append(_entry("short", record, sequence[:150], " (first 150)"))
        elif number < 12:
            entries.append(
                _entry(
                    "reverse",
                    record,
                    sequence.translate(COMPLEMENT)[::-1],
                    " (reverse)",
                )
            )
        else:
            start = chance.randrange(0, len(sequence) - 300 + 1)
            entries.append(
                _entry(
                    "window",
                    record,
                    sequence[start : start + 300],
                    f" (bases {start + 1}-{start + 300})",
                )
            )

    # Other genes: the marker check must decline them
    for gene in (g for g in genes if g != "CO1"):
        entries += [
            _entry(f"gene-{gene}", r, r["sequence"])
            for r in _add_sequences(
                gene, _pick(_records(gene), 2, "order", taken, known)
            )
        ]

    GOLDEN.mkdir(parents=True, exist_ok=True)
    with SEQUENCES.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"Chose {len(entries)} sequences: {SEQUENCES.relative_to(ROOT)}")


def _read(path: Path) -> list[Record]:
    if not path.exists():
        sys.exit(f"Missing {path.relative_to(ROOT)}")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _without_timings(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_timings(v) for k, v in value.items() if k != "seconds"}
    if isinstance(value, list):
        return [_without_timings(v) for v in value]
    return value


def _answers(bundle: Path) -> Iterator[tuple[str, Any]]:
    identifier = load_bundle(bundle).identifier
    for entry in _read(SEQUENCES):
        result = identifier.identify(entry["sequence"])
        yield entry["id"], _without_timings(json.loads(result.model_dump_json()))


def write(bundle: Path, force: bool) -> None:
    if ANSWERS.exists() and not force:
        sys.exit(f"{ANSWERS.name} exists; run check, review, then use --force")
    with ANSWERS.open("w", encoding="utf-8") as handle:
        for entry_id, result in _answers(bundle):
            handle.write(
                json.dumps({"id": entry_id, "result": result}, sort_keys=True) + "\n"
            )
    print(f"Wrote {len(_read(ANSWERS))} answers: {ANSWERS.relative_to(ROOT)}")


def _differences(path: str, old: Any, new: Any) -> Iterator[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            yield from _differences(f"{path}.{key}", old.get(key), new.get(key))
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for number, (a, b) in enumerate(zip(old, new, strict=True)):
            yield from _differences(f"{path}[{number}]", a, b)
    elif old != new:
        yield f"{path}: {json.dumps(old)[:100]} -> {json.dumps(new)[:100]}"


def check(bundle: Path, show: int) -> None:
    expected = {row["id"]: row["result"] for row in _read(ANSWERS)}
    changed = 0
    for entry_id, result in _answers(bundle):
        if entry_id not in expected:
            sys.exit(f"{entry_id} has no recorded answer: run write --force")
        found = list(_differences("", expected[entry_id], result))
        if found:
            changed += 1
            print(f"CHANGED {entry_id} ({len(found)} differences)")
            for line in found[:show]:
                print(f"  {line}")
    total = len(expected)
    if changed:
        sys.exit(f"{changed} of {total} answers changed")
    print(f"All {total} answers are identical")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("select").add_argument("--force", action="store_true")
    for name in ("write", "check"):
        command = commands.add_parser(name)
        command.add_argument("--bundle", type=Path, default=BUNDLE)
        if name == "write":
            command.add_argument("--force", action="store_true")
        else:
            command.add_argument(
                "--show", type=int, default=5, help="Differences to show per answer"
            )
    args = parser.parse_args()
    if args.command == "select":
        select(args.force)
    elif args.command == "write":
        write(args.bundle, args.force)
    else:
        check(args.bundle, args.show)


if __name__ == "__main__":
    main()
