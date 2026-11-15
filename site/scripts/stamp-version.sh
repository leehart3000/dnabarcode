#!/usr/bin/env bash
# Writes the site version into the pages' footers, from git:
#   at a release tag           v1.0.0  ->  1.0.0/8fdab8a
#   two commits after it               ->  1.0.0+2/8fdab8a
#   before any release tag             ->  0.0.0+<commits>/8fdab8a
# Prints the version. Used by the Release workflow before deploying; for a
# deploy by hand, run it, deploy, then `git restore site/public`.
set -euo pipefail
cd "$(dirname "$0")/.."

sha="$(git rev-parse --short=7 HEAD)"
described="$(git describe --tags --long --match 'v[0-9]*' 2>/dev/null || true)"
if [[ -z "$described" ]]; then
  version="0.0.0+$(git rev-list --count HEAD)/$sha"
else
  tag="${described%-*-g*}"          # v1.0.0
  rest="${described#"$tag"-}"       # 2-g8fdab8a
  count="${rest%%-*}"               # 2
  base="${tag#v}"
  if [[ "$count" == "0" ]]; then
    version="$base/$sha"
  else
    version="$base+$count/$sha"
  fi
fi

for page in public/*.html; do
  sed -i.bak "s|<span data-version>[^<]*</span>|<span data-version>$version</span>|" "$page"
  rm "$page.bak"
done
echo "$version"
