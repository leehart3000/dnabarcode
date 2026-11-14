# Google Cloud setup

How DNAbarcode.org's Google Cloud resources were created, so they can be
checked or rebuilt. Each product has its own project; the `prokoptonml`
project holds only the platform's own services. Commands are run once, by
hand, from the repository root, with `gcloud` signed in as the owner.
Nothing here holds a secret: the API key lives only in Secret Manager.

| Setting | Value |
|---|---|
| Project | `dnabarcode` (display name "DNAbarcode") |
| Region | `europe-west2` (London) |
| Budget | `dnabarcode-monthly`: £10 a month, alerts at 50/90/100% (console) |
| Spend cap | `dnabarcode-spend-cap`: Cloud Run, £10 (console) |

## 1. Project

Display names may not contain a full stop.

```bash
gcloud projects create dnabarcode --name="DNAbarcode"
BILLING="$(gcloud billing accounts list --filter=open=true --format='value(name)' | head -1)"
gcloud billing projects link dnabarcode --billing-account="$BILLING"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com \
    iamcredentials.googleapis.com sts.googleapis.com --project=dnabarcode
```

## 2. Images and bundles

Images go to `europe-west2-docker.pkg.dev/dnabarcode/images`. The cleanup
policy keeps the 5 newest images and deletes others after 7 days
(`set-cleanup-policies` only previews a policy without `--no-dry-run`).
Serving bundles are built locally (they need the full data and the MLflow
registry) and kept in a private bucket, one dated folder each (`<date>/`);
CI downloads the one named in `infra/deploy/dnabarcode.env` and checks it
against its manifest. Old bundles are removed by hand, never the one in use.

```bash
gcloud artifacts repositories create images --project=dnabarcode \
    --repository-format=docker --location=europe-west2 \
    --description="DNAbarcode.org service images"
gcloud artifacts repositories set-cleanup-policies images --project=dnabarcode \
    --location=europe-west2 \
    --policy=infra/gcp/artifact-registry-cleanup-policy.json --no-dry-run
gcloud storage buckets create gs://dnabarcode-bundles --project=dnabarcode \
    --location=europe-west2 --uniform-bucket-level-access --public-access-prevention
gcloud storage rsync data/models/dnabarcode/bundle \
    gs://dnabarcode-bundles/<YYYY-MM-DD> --recursive
```

## 3. API key, identities and trust

- `dnabarcode-api`: the service's runtime identity; it can only read its
  own API key.
- `github-deployer`: CI's identity. Push to this project's image
  repository; read this project's bundle bucket; act as `dnabarcode-api`
  only; `run.developer` on the project for the first deploy (which creates
  the service), then on the one service only (see 4).
- Workload Identity Federation: pool `github`, provider
  `dnabarcode-releases`, accepting only `leehart3000/dnabarcode` (by its
  fixed numeric ID) on `main` and on `v*` release tags. No stored Google keys.

```bash
P=dnabarcode
NUMBER="$(gcloud projects describe $P --format='value(projectNumber)')"
REPO_ID="$(gh api repos/leehart3000/dnabarcode --jq .id)"
DEPLOYER="github-deployer@$P.iam.gserviceaccount.com"
RUNTIME="dnabarcode-api@$P.iam.gserviceaccount.com"
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create dnabarcode-api-key --project=$P \
    --replication-policy=user-managed --locations=europe-west2 --data-file=-
gcloud iam service-accounts create dnabarcode-api --project=$P \
    --display-name="dnabarcode API (Cloud Run runtime)"
gcloud iam service-accounts create github-deployer --project=$P \
    --display-name="GitHub Actions deployer"
gcloud secrets add-iam-policy-binding dnabarcode-api-key --project=$P \
    --member="serviceAccount:$RUNTIME" --role=roles/secretmanager.secretAccessor
gcloud artifacts repositories add-iam-policy-binding images --project=$P \
    --location=europe-west2 --member="serviceAccount:$DEPLOYER" \
    --role=roles/artifactregistry.writer
gcloud storage buckets add-iam-policy-binding gs://dnabarcode-bundles \
    --member="serviceAccount:$DEPLOYER" --role=roles/storage.objectViewer
gcloud iam service-accounts add-iam-policy-binding $RUNTIME --project=$P \
    --member="serviceAccount:$DEPLOYER" --role=roles/iam.serviceAccountUser
gcloud projects add-iam-policy-binding $P --member="serviceAccount:$DEPLOYER" \
    --role=roles/run.developer --condition=None
gcloud iam workload-identity-pools create github --project=$P --location=global \
    --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc dnabarcode-releases \
    --project=$P --location=global --workload-identity-pool=github \
    --display-name="dnabarcode main and release tags" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository_id=='$REPO_ID' && (assertion.ref=='refs/heads/main' || assertion.ref.startsWith('refs/tags/v'))"
gcloud iam service-accounts add-iam-policy-binding $DEPLOYER --project=$P \
    --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/$NUMBER/locations/global/workloadIdentityPools/github/attribute.repository_id/$REPO_ID"
```

## 4. First deploy, then make it public and narrow the deployer

`.github/workflows/deploy-dnabarcode.yml` (settings in
`infra/deploy/dnabarcode.env`) downloads and checks the bundle, builds the
image with the platform from PyPI, tests it, pushes it, deploys it by digest
and checks the live service. The first deploy runs with `check_public` off:
the service starts private, because the deployer cannot change who may call
it. Then, once:

```bash
P=dnabarcode
DEPLOYER="github-deployer@$P.iam.gserviceaccount.com"
# Anyone may reach the service; /identify still needs the API key
gcloud run services add-iam-policy-binding dnabarcode-api --project=$P \
    --region europe-west2 --member=allUsers --role=roles/run.invoker
# Narrow the deployer from the whole project to this one service
gcloud run services add-iam-policy-binding dnabarcode-api --project=$P \
    --region europe-west2 --member="serviceAccount:$DEPLOYER" --role=roles/run.developer
gcloud projects remove-iam-policy-binding $P \
    --member="serviceAccount:$DEPLOYER" --role=roles/run.developer --condition=None
```

The Cloudflare Worker (`sites/dnabarcode/`) then gets the service's address
(`API_URL` in `wrangler.jsonc`) and the key, piped from Secret Manager:

```bash
gcloud secrets versions access latest --secret=dnabarcode-api-key --project=dnabarcode \
    | npx --yes wrangler@4.162.0 secret put API_KEY --config sites/dnabarcode/wrangler.jsonc
```

## History

Until November 2026, DNAbarcode.org ran in the `prokoptonml` project and was
deployed from the `prokoptonml` repository. It moved to its own repository
(installing the platform from PyPI) and then to this project, so that the
`prokoptonml` project holds only the platform's own services.

The local `data/` folder (raw and processed data, bundles and the MLflow
registry) was then moved into this working copy. MLflow records absolute
paths, so they were rewritten with `scripts/relocate_mlflow.py` (which backs
up the database first). The next step is to keep MLflow's artifacts and
database off the laptop (a Cloud Storage bucket or a hosted MLflow), so no
folder path matters.
