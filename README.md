# DNAbarcode.org

[![CI](https://github.com/leehart3000/dnabarcode/actions/workflows/ci.yml/badge.svg)](https://github.com/leehart3000/dnabarcode/actions/workflows/ci.yml)

**[DNAbarcode.org](https://dnabarcode.org)** identifies animals from COI DNA
barcodes, with cautious, explained answers: a species where the reference
data and this marker can tell, and a broader group where they can't.
Species-level answers cover mosquitoes (family Culicidae) for now.

It is a product of **ProkoptonML**, an open MLOps platform: the models are
built, evaluated and packaged with the platform
([`prokopton-ml`](https://pypi.org/project/prokopton-ml/), from
[leehart3000/prokoptonml](https://github.com/leehart3000/prokoptonml)),
and this repository holds everything specific to DNAbarcode.org.

## How it fits together

```
MIDORI2 + NCBI RefSeq ─► prokopton-ml pipeline (pixi tasks in this repo)
                       ─► model cards + serving bundle ─► Cloud Storage
                       ─► CI: check bundle → image (platform from PyPI + bundle)
                          → test → Cloud Run
Visitor ─► DNAbarcode.org (Cloudflare Worker: pages, firewall rate limit,
           Turnstile) ─► API key ─► Cloud Run ─► answer + decision trace
```

## Repository layout

| Path | Contents |
|---|---|
| `apps/dnabarcode/` | The app config, reviewed reference files, model cards and known-answer checks |
| `analysis/` | One-off analyses, with each question, finding and decision |
| `sites/dnabarcode/` | The website and API gateway (Cloudflare Worker), with unit and browser tests |
| `infra/` | Google Cloud setup runbook and deploy settings |
| `docs/` | How to release and operate DNAbarcode.org |
| `Dockerfile` | The API image: `prokopton-ml` from PyPI plus the serving bundle |
| `pixi.toml` | The environment (platform pinned exactly) and the pipeline tasks |

## Working on it

```bash
pixi install          # the environment, with prokopton-ml from PyPI
pixi run check        # format, lint, and check the config against the platform
pixi run dnabarcode-culicidae-evaluate   # one of the pipeline stages
```

The pipeline reads and writes `data/` (never committed). If that folder
moves, run `scripts/relocate_mlflow.py` to update the absolute paths MLflow
stores. Releasing and
operating the live service: [`docs/releasing-dnabarcode.md`](docs/releasing-dnabarcode.md).

## Model cards

- [Culicidae specialist](apps/dnabarcode/model-cards/culicidae.md), with
  its [development notes](apps/dnabarcode/model-cards/culicidae-notes.md)

## Licence

Copyright (C) 2026 Lee Hart

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, version 3 only. See the [LICENSE](LICENSE) file.

SPDX-License-Identifier: `AGPL-3.0-only`

Reference data: MIDORI2 (GenBank release 273; Leray et al. 2022; CC BY 4.0)
and NCBI RefSeq. Data and trained models may be subject to separate
licences, which are documented alongside them.
