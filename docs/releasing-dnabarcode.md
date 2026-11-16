# Releasing and operating DNAbarcode.org

Step-by-step guides for the common jobs. Commands run from the repository
root on a Mac with `pixi`, `gcloud` (signed in as the project owner, with
`gcloud config set project dnabarcode`), `gh` and Node 22+. Nothing here
prints a secret.

| Part | Where it runs | How it is deployed |
|---|---|---|
| Models and references (the bundle) | Built locally | Uploaded to `gs://dnabarcode-bundles/<date>/` |
| API | Cloud Run `dnabarcode-api`, project `dnabarcode`, `europe-west2` | A release (`v*` tag), or `deploy-dnabarcode.yml` by hand from `main` |
| Website and gateway | Cloudflare Worker `dnabarcode-site` | A release (`v*` tag), or `wrangler deploy` from a Mac |

## 0. Make a release

Releases are numbered `vMAJOR.MINOR.PATCH`. Tagging a commit on `main`
starts `.github/workflows/release.yml`, which deploys the API, deploys the
website and gateway with the version in the footer (`1.0.0/8fdab8a`), runs
the browser tests against the live site and records a GitHub Release with
the version, bundle and platform version. Tags are permanent (the "Protect
release tags" ruleset), so a fix is always a new version.

```bash
git switch main && git pull
pixi run release v1.0.1
```

The command (`prokopton-ml release`, from the platform) stops before tagging unless you are on `main` with no
uncommitted changes, `main` matches GitHub, the version is new and the
commit has not been released already. It then waits for the Release
workflow and checks that the live footer shows the new version. The
workflow checks the same again (the tag must be on `main`, and its commit
must not carry another release tag), in case a tag is pushed by hand.

The Cloudflare token used by the release lives only in the `production`
environment, which only `v*` tags can use.

## 1. Release a new bundle (new models or reference data)

1. Make the change (config, data, code) in a pull request, as usual.
2. Rebuild what changed. For the mosquito specialist:

   ```bash
   pixi run dnabarcode-culicidae-anchors      # only to refresh the RefSeq anchors
   pixi run dnabarcode-culicidae-reference
   pixi run dnabarcode-culicidae-evaluate     # chooses the thresholds
   pixi run dnabarcode-culicidae-card         # refuses if the config's thresholds differ
   ```

   The router and marker models have their own `dnabarcode-*` and
   `dnabarcode-marker-*` tasks (sample, train, calibrate, evaluate, card).
3. Commit the updated model cards, then build and upload the bundle under a
   new dated folder (never overwrite one that is in use):

   ```bash
   pixi run dnabarcode-bundle
   gcloud storage rsync data/models/dnabarcode/bundle \
       gs://dnabarcode-bundles/<YYYY-MM-DD> --recursive
   ```

4. Compare the new bundle's answers with the golden set
   (`tests/golden/`): `pixi run golden-check` lists every changed
   answer. If no answer should change (a new platform version, say), it must
   report none. If answers are expected to change, review every difference,
   then record them with `pixi run python scripts/golden.py write --force`.
5. In a pull request, set `BUNDLE=` in `infra/deploy/dnabarcode.env` to the
   new folder. If answers are expected to change, update or add known-answer
   checks in `tests/known-answers/`, and include the new golden answers.
6. After merging, make a release (section 0), or deploy only the API and watch:

   ```bash
   gh workflow run deploy-dnabarcode.yml --ref main -f check_public=true
   gh run watch "$(gh run list --workflow=deploy-dnabarcode.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

   The workflow (the platform's `deploy-cloud-run.yml`, pinned to a platform
   release) checks the bundle against its manifest, tests the image (health,
   key required, and the known answers with `prokopton-ml check`) before
   pushing it, deploys it by digest and checks the live service. To run the
   known-answer checks against the local bundle first: `pixi run known-answers`.
7. Run the browser tests: `gh workflow run site.yml --ref main`.

## 2. Change the website or gateway

1. Change `site/` in a pull request (the unit tests run in CI).
   Optionally run the browser tests against a local preview first.
2. After merging, make a release (section 0). To deploy by hand instead
   (the footer then shows, for example, `1.0.0+2/8fdab8a`):

   ```bash
   site/scripts/stamp-version.sh
   npx --yes wrangler@4.162.0 deploy --config site/wrangler.jsonc
   git restore site/public
   gh workflow run site.yml --ref main
   ```

## 3. Roll back

- **API:** list revisions and send all traffic to the previous one:

  ```bash
  gcloud run revisions list --service dnabarcode-api --region europe-west2
  gcloud run services update-traffic dnabarcode-api --region europe-west2 --to-revisions <REVISION>=100
  ```

  The next deploy sends traffic to the new revision again.
- **Website:** `npx --yes wrangler@4.162.0 rollback --config site/wrangler.jsonc`
  (choose the version to return to).

## 4. Replace the API key

Do this if the key may have leaked. Identifications fail for a minute or
two while the two sides switch over.

```bash
openssl rand -hex 32 | tr -d '\n' | gcloud secrets versions add dnabarcode-api-key --data-file=-
gcloud secrets versions access latest --secret=dnabarcode-api-key \
    | npx --yes wrangler@4.162.0 secret put API_KEY --config site/wrangler.jsonc
gcloud run services update dnabarcode-api --region europe-west2 \
    --update-secrets PROKOPTON_API_KEY=dnabarcode-api-key:latest
gcloud secrets versions list dnabarcode-api-key       # then disable the old version:
gcloud secrets versions disable <OLD_VERSION> --secret=dnabarcode-api-key
```

The Turnstile secret is replaced in the Cloudflare dashboard (Turnstile >
the widget > rotate secret), then with
`npx --yes wrangler@4.162.0 secret put TURNSTILE_SECRET --config site/wrangler.jsonc`.

## 5. Look at what is happening

```bash
# API logs (JSON lines; sequences are never logged)
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="dnabarcode-api"' --limit 30 --freshness 1d
# Gateway logs, live
npx --yes wrangler@4.162.0 tail --config site/wrangler.jsonc
```

## 6. Costs and limits

- Cloud Run: 1 CPU, 2 GiB, 4 requests at a time, 0 to 2 instances (scale to
  zero). Settings in `infra/deploy/dnabarcode.env`.
- Cold start: an idle service took 12–13 s to answer (November 2026): 7–10 s
  to start the container and import Python, and 3–5 s to load the bundle.
  Warm requests take about 0.1 s, or 0.2–0.35 s through the site. The
  identify page wakes the service when it opens (`/api/health`), and the page explains a
  slow first answer after 4 s.
- Startup CPU boost was tried (v1.0.4) and did not shorten the cold start
  (13.1 s against 12.3 s), so it is turned off (`--no-cpu-boost`; leaving the
  flag out would keep the previous setting). Keeping one instance always
  running would remove cold starts, but would cost most of the monthly budget.
- Firewall rate limit: 5 identifications per 10 seconds per IP (Cloudflare
  dashboard); every identification also needs a Turnstile token.
- Budget: £10 a month on the `dnabarcode` project (alerts), plus a £10
  Cloud Run spend cap.
- Storage: old bundles and images are cleaned up as described in
  [`infra/gcp/README.md`](../infra/gcp/README.md).
