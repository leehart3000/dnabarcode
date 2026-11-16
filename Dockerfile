# The DNAbarcode.org API: the ProkoptonML platform from PyPI, serving this
# product's prebuilt bundle.
#
# Build from the repository root with the serving bundle in ./bundle (CI
# downloads it and checks its manifest first):
#   docker build -t dnabarcode-api .
# Cloud Run sets PORT; locally, docker run -p 8080:8080 dnabarcode-api

FROM python:3.13-slim

# The platform version, pinned exactly (the same as in pixi.toml)
ARG PROKOPTON_ML_VERSION=0.2.0a3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PROKOPTON_BUNDLE=/srv/bundle \
    PROKOPTON_API_TITLE="DNAbarcode.org API"

WORKDIR /srv

# The exact package versions the models were saved with come first, so
# this layer is reused while the bundle's requirements stay the same
COPY bundle/requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt

# The platform from PyPI, without its training dependencies (MLflow is not
# needed to serve)
RUN pip install --no-deps "prokopton-ml==${PROKOPTON_ML_VERSION}"

COPY bundle /srv/bundle

# Run as an unprivileged user
RUN useradd --system --uid 10001 --no-create-home api
USER api

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn --factory prokopton.ml.serving.app:create_app_from_env --host 0.0.0.0 --port ${PORT:-8080}"]
