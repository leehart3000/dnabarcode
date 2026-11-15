"""Checks that need the platform installed: the app config is valid for the
pinned platform version, and the Dockerfile installs that same version.

Run with `pixi run check-config` (part of `pixi run check`).
"""

import re
import sys
import tomllib
from pathlib import Path

from prokopton.core.config import load_config
from prokopton.ml import __version__
from prokopton.ml.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    config = load_config(ROOT / "prokopton.toml", AppConfig)
    print(f"Config OK: {config.name}, for prokopton-ml {__version__}")

    pinned = tomllib.loads((ROOT / "pixi.toml").read_text("utf-8"))[
        "pypi-dependencies"
    ]["prokopton-ml"]["version"].removeprefix("==")
    found = re.search(
        r"^ARG PROKOPTON_ML_VERSION=(\S+)$",
        (ROOT / "Dockerfile").read_text("utf-8"),
        re.MULTILINE,
    )
    docker = found.group(1) if found else "(missing)"
    if not pinned == docker == __version__:
        sys.exit(
            f"Platform versions differ: pixi.toml {pinned}, Dockerfile {docker}, "
            f"installed {__version__}"
        )
    print(f"Platform version {pinned} matches in pixi.toml and the Dockerfile")


if __name__ == "__main__":
    main()
