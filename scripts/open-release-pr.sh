#!/usr/bin/env bash
# Push the local semantic-release commit to a release branch and open a
# pull request. main is protected, so the version bump cannot land there.
# Merging the pull request is the release.
#
# The release branch is replaced on every run. It has to be the version
# bump on top of current main. An older branch would drop later fixes
# when the pull request is squash-merged.
set -euo pipefail

VERSION="${VERSION:-}"
REPO="${GH_REPO:-${GITHUB_REPOSITORY:-}}"
DRY_RUN="${DRY_RUN:-0}"

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "VERSION must look like X.Y.Z: ${VERSION}" >&2
  exit 1
fi

if [ -z "${REPO}" ]; then
  echo "GH_REPO or GITHUB_REPOSITORY required" >&2
  exit 1
fi

BRANCH="chore/release-${VERSION}"
echo "PLAN: release pull request ${BRANCH} on ${REPO}"

if [ "${DRY_RUN}" = "1" ]; then
  echo "DO: git push --force origin HEAD:refs/heads/${BRANCH}"
  echo "DO: gh pr create --repo ${REPO} --base main --head ${BRANCH} --title chore(release): v${VERSION}"
  echo "OK: dry run"
  exit 0
fi

echo "DO: push ${BRANCH}"
git push --force origin "HEAD:refs/heads/${BRANCH}"

existing="$(gh pr list --repo "${REPO}" --head "${BRANCH}" --base main --state open --json number --jq '.[0].number // empty')"
if [ -n "${existing}" ]; then
  echo "OK: pull request #${existing} already open"
  exit 0
fi

echo "DO: create pull request"
body_file="$(mktemp)"
cleanup() { rm -f "${body_file}"; }
trap cleanup EXIT
cat >"${body_file}" <<EOF
Version bump for the commits already on main.

Merging this pull request is the release. The Release workflow tags that commit and publishes the GitHub Release after the merge. It does not publish from this branch.

PyPI project name minidb belongs to another package. The publish step is allowed to fail.
EOF
gh pr create --repo "${REPO}" --base main --head "${BRANCH}" \
  --title "chore(release): v${VERSION}" \
  --body-file "${body_file}"
echo "OK: opened ${BRANCH}"
