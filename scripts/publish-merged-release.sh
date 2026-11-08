#!/usr/bin/env bash
# Tag and publish the commit that merged chore(release).
# The workflow trigger is push to main, so the tag push does not
# start another Release run. Do not call this for a version bump
# that is still on a pull request branch.
set -euo pipefail

REPO="${GH_REPO:-${GITHUB_REPOSITORY:-}}"
DRY_RUN="${DRY_RUN:-0}"
TARGET="${GITHUB_SHA:-HEAD}"

if [ ! -f pyproject.toml ]; then
  echo "pyproject.toml not found in $(pwd)" >&2
  exit 1
fi

if [ -z "${REPO}" ]; then
  echo "GH_REPO or GITHUB_REPOSITORY required" >&2
  exit 1
fi

VERSION="$(
  python3 - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "project.version must look like X.Y.Z: ${VERSION}" >&2
  exit 1
fi

TAG="v${VERSION}"
echo "PLAN: GitHub Release ${TAG} at ${TARGET} on ${REPO}"

notes_file="$(mktemp)"
cleanup() { rm -f "${notes_file}"; }
trap cleanup EXIT

# Prefer the changelog section semantic-release wrote into this commit.
# GitHub's generated notes are the fallback when that section is absent.
if python3 - "${VERSION}" "${notes_file}" <<'PY'
import sys
from pathlib import Path

version, dest = sys.argv[1], sys.argv[2]
changelog = Path("CHANGELOG.md")
if not changelog.is_file():
    sys.exit(2)
text = changelog.read_text(encoding="utf-8")
header = f"## v{version}"
start = text.find(header)
if start < 0:
    sys.exit(2)
lines = text[start:].splitlines(True)
body = [lines[0]]
for line in lines[1:]:
    if line.startswith("## "):
        break
    body.append(line)
Path(dest).write_text("".join(body).strip() + "\n", encoding="utf-8")
PY
then
  notes_label="--notes-file ${notes_file}"
else
  notes_label="--generate-notes"
fi

if [ "${DRY_RUN}" = "1" ]; then
  echo "DO: gh release create ${TAG} --repo ${REPO} --target ${TARGET} --title ${TAG} ${notes_label}"
  echo "OK: dry run"
  exit 0
fi

if gh release view "${TAG}" --repo "${REPO}" >/dev/null 2>&1; then
  echo "OK: release ${TAG} already exists"
  exit 0
fi

echo "DO: create GitHub Release ${TAG}"
if [ "${notes_label}" = "--generate-notes" ]; then
  gh release create "${TAG}" --repo "${REPO}" --target "${TARGET}" \
    --title "${TAG}" --generate-notes
else
  gh release create "${TAG}" --repo "${REPO}" --target "${TARGET}" \
    --title "${TAG}" --notes-file "${notes_file}"
fi
echo "OK: published ${TAG}"
