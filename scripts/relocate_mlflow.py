"""Rewrite the absolute paths that MLflow stores, after moving its folder.

MLflow records full ``file://`` paths to its artifacts in the tracking
database (experiments, runs, logged models and model versions) and in each
logged model's ``MLmodel`` file. After moving ``data/`` to another folder,
those paths must change too, or models can't be loaded from the registry.

Dry run (the default) reports what would change; ``--apply`` backs up the
database, rewrites the database and the ``MLmodel`` files, and checks that
no old path remains.

    pixi run python scripts/relocate_mlflow.py OLD_DATA_DIR NEW_DATA_DIR [--apply]
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# The columns where MLflow stores artifact locations (checked by scanning
# every text column before this script was written)
COLUMNS = (
    ("experiments", "artifact_location"),
    ("runs", "artifact_uri"),
    ("logged_models", "artifact_location"),
    ("model_versions", "storage_location"),
    ("model_versions", "source"),
)


def model_files(mlflow_dir: Path) -> list[Path]:
    return sorted(mlflow_dir.rglob("MLmodel"))


def count_old(con: sqlite3.Connection, old: str) -> dict[str, int]:
    counts = {}
    for table, column in COLUMNS:
        exists = con.execute(
            "select count(*) from pragma_table_info(?) where name = ?", (table, column)
        ).fetchone()[0]
        if exists:
            counts[f"{table}.{column}"] = con.execute(
                f'select count(*) from "{table}" where instr("{column}", ?) > 0',
                (old,),
            ).fetchone()[0]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("old", help="The data folder's old absolute path")
    parser.add_argument("new", type=Path, help="The data folder's new location")
    parser.add_argument("--apply", action="store_true", help="Make the changes")
    args = parser.parse_args()

    old = args.old.rstrip("/")
    new = str(args.new.resolve())
    mlflow_dir = Path(new) / "mlflow"
    db = mlflow_dir / "mlflow.db"
    if not db.is_file():
        sys.exit(f"No MLflow database at {db}: move the data folder first")
    if old == new:
        sys.exit("The old and new paths are the same")

    con = sqlite3.connect(db)
    before = count_old(con, old)
    files = [f for f in model_files(mlflow_dir) if old in f.read_text("utf-8")]
    print(f"Old path: {old}\nNew path: {new}")
    for name, count in before.items():
        print(f"  {name}: {count} rows")
    print(f"  MLmodel files: {len(files)}")
    if not args.apply:
        print("Dry run: nothing changed. Run again with --apply.")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db.with_name(f"mlflow.db.before-relocate-{stamp}")
    con.close()
    shutil.copy2(db, backup)
    print(f"Backed up the database to {backup.name}")

    con = sqlite3.connect(db)
    with con:
        for table, column in COLUMNS:
            if f"{table}.{column}" in before:
                con.execute(
                    f'update "{table}" set "{column}" = replace("{column}", ?, ?) '
                    f'where instr("{column}", ?) > 0',
                    (old, new, old),
                )
    for path in files:
        path.write_text(path.read_text("utf-8").replace(old, new), "utf-8")

    after = count_old(con, old)
    left = [f for f in model_files(mlflow_dir) if old in f.read_text("utf-8")]
    con.close()
    remaining = sum(after.values()) + len(left)
    print(f"Rewrote {sum(before.values())} rows and {len(files)} MLmodel files")
    if remaining:
        sys.exit(f"{remaining} references to the old path remain")
    print("No references to the old path remain")


if __name__ == "__main__":
    main()
