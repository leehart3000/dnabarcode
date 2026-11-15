#!/usr/bin/env bash
# Release DNAbarcode.org: tag main, wait for the Release workflow and check
# the live footer. Stops at the first problem (nothing after it runs).
#
#   scripts/release.sh v1.0.10
#
# Before tagging, it checks that you are on main with no uncommitted changes,
# that main matches GitHub, that the version is new, and that this commit has
# not been released already (so a release always contains something new).
set -euo pipefail

stop() { echo "STOP: $*" >&2; exit 1; }

[ $# -eq 1 ] || stop "usage: scripts/release.sh vMAJOR.MINOR.PATCH"
tag=$1
[[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || stop "not a version like v1.2.3: $tag"

cd "$(git rev-parse --show-toplevel)"
[ "$(git branch --show-current)" = main ] || stop "not on main (git switch main)"
[ -z "$(git status --porcelain)" ] || stop "uncommitted changes (see git status)"
git fetch --quiet --tags origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] \
  || stop "main differs from GitHub (git pull)"
! git rev-parse --quiet --verify "refs/tags/$tag" > /dev/null || stop "$tag already exists"
released=$(git tag --points-at HEAD --list 'v*' | paste -sd ' ' -)
[ -z "$released" ] || stop "this commit is already released as $released"
last=$(git describe --tags --abbrev=0 --match 'v*' 2> /dev/null || true)
echo "Changes since ${last:-the first commit}:"
git log --oneline "${last:+$last..}HEAD"

git tag -a "$tag" -m "DNAbarcode.org ${tag#v}"
git push --quiet origin "$tag"
run=
for _ in $(seq 1 24); do
  run=$(gh run list --workflow=release.yml --branch "$tag" --json databaseId --jq '.[0].databaseId // empty')
  [ -n "$run" ] && break
  sleep 5
done
[ -n "$run" ] || stop "no Release run started for $tag (gh run list --workflow=release.yml)"
echo "Release run $run: waiting (about 8 minutes)"
gh run watch "$run" --exit-status > /dev/null || stop "the release failed (gh run view $run --log-failed)"

expected="${tag#v}/$(git rev-parse --short=7 HEAD)"
for _ in 1 2 3 4 5 6; do
  live=$(curl --silent https://dnabarcode.org/ | sed -n 's/.*<span data-version>\([^<]*\)<\/span>.*/\1/p')
  [ "$live" = "$expected" ] && break
  sleep 10
done
[ "$live" = "$expected" ] || stop "the live footer shows ${live:-nothing}, not $expected"
echo "Released $tag: the live site shows $live"
