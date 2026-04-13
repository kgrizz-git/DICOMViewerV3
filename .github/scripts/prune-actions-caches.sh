#!/usr/bin/env bash
# Prune GitHub Actions dependency caches that are unlikely to be reused.
#
# Inputs (environment):
#   GITHUB_REPOSITORY  owner/name (set by Actions)
#   GITHUB_TOKEN       token with actions:write (set by Actions)
#   MIN_AGE_DAYS       delete only if last_accessed_at (or created_at) is older than this many days
#   DRY_RUN            if 1/true/yes, print candidates but do not call DELETE
#   EXTRA_PROTECTED_REFS  optional space-separated full refs to never delete
#
# Policy: never delete caches whose ref is the repo default branch, refs/heads/develop,
# or any EXTRA_PROTECTED_REFS entry. All other refs (PR merge refs, feature branches, tags,
# etc.) may be removed once stale by last access time.

set -euo pipefail

: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_TOKEN:?}"
MIN_AGE_DAYS="${MIN_AGE_DAYS:-7}"
DRY_RUN="${DRY_RUN:-0}"
EXTRA_PROTECTED_REFS="${EXTRA_PROTECTED_REFS:-}"

OWNER="${GITHUB_REPOSITORY%%/*}"
REPO="${GITHUB_REPOSITORY##*/}"
API_ROOT="https://api.github.com/repos/${OWNER}/${REPO}"
CURL_AUTH=(
  -H "Authorization: Bearer ${GITHUB_TOKEN}"
  -H "Accept: application/vnd.github+json"
  -H "X-GitHub-Api-Version: 2022-11-28"
)

case "${DRY_RUN,,}" in
  1 | true | yes) DRY_RUN=1 ;;
  *) DRY_RUN=0 ;;
esac

if ! [[ "${MIN_AGE_DAYS}" =~ ^[0-9]+$ ]] || [ "${MIN_AGE_DAYS}" -lt 0 ]; then
  echo "MIN_AGE_DAYS must be a non-negative integer, got: ${MIN_AGE_DAYS}" >&2
  exit 1
fi

DEFAULT_BRANCH="$(curl -fsS "${CURL_AUTH[@]}" "${API_ROOT}" | jq -r '.default_branch')"
if [ -z "${DEFAULT_BRANCH}" ] || [ "${DEFAULT_BRANCH}" = "null" ]; then
  echo "Could not resolve default_branch from GitHub API." >&2
  exit 1
fi

PROTECTED_FILE="$(mktemp)"
cleanup() { rm -f "${PROTECTED_FILE}"; }
trap cleanup EXIT

{
  printf '%s\n' "refs/heads/${DEFAULT_BRANCH}"
  printf '%s\n' "refs/heads/develop"
  # shellcheck disable=SC2086
  for r in ${EXTRA_PROTECTED_REFS}; do
    [ -n "${r}" ] && printf '%s\n' "${r}"
  done
} | sort -u > "${PROTECTED_FILE}"

is_protected_ref() {
  grep -Fxq "$1" "${PROTECTED_FILE}"
}

now_epoch="$(date -u +%s)"
cutoff_epoch=$((now_epoch - MIN_AGE_DAYS * 86400))

echo "Default branch: ${DEFAULT_BRANCH} (protected ref refs/heads/${DEFAULT_BRANCH})"
echo "Also protecting refs/heads/develop and: ${EXTRA_PROTECTED_REFS:-<none>}"
echo "MIN_AGE_DAYS=${MIN_AGE_DAYS} DRY_RUN=${DRY_RUN}"

pruned=0
skipped_protected=0
skipped_fresh=0
page=1

while true; do
  json="$(
    curl -fsS "${CURL_AUTH[@]}" \
      "${API_ROOT}/actions/caches?per_page=100&page=${page}&sort=last_accessed_at&direction=asc"
  )"
  count="$(jq '.actions_caches | length' <<<"${json}")"
  if [ "${count}" -eq 0 ]; then
    break
  fi

  while IFS= read -r row; do
    cid="$(jq -r '.id' <<<"${row}")"
    ref="$(jq -r '.ref' <<<"${row}")"
    key="$(jq -r '.key' <<<"${row}")"
    sz="$(jq -r '.size_in_bytes' <<<"${row}")"
    ts="$(jq -r '.last_accessed_at // .created_at' <<<"${row}")"
    if [ -z "${ts}" ] || [ "${ts}" = "null" ]; then
      echo "skip id=${cid} (missing timestamps) ref=${ref} key=${key}"
      continue
    fi
    tepoch="$(date -u -d "${ts}" +%s)"

    if is_protected_ref "${ref}"; then
      skipped_protected=$((skipped_protected + 1))
      continue
    fi
    if [ "${tepoch}" -gt "${cutoff_epoch}" ]; then
      skipped_fresh=$((skipped_fresh + 1))
      continue
    fi

    echo "stale non-protected cache: id=${cid} ref=${ref} key=${key} size_bytes=${sz} last_or_created=${ts}"
    pruned=$((pruned + 1))
    if [ "${DRY_RUN}" -eq 1 ]; then
      continue
    fi
    code="$(
      curl -fsS -o /dev/null -w "%{http_code}" -X DELETE \
        "${CURL_AUTH[@]}" "${API_ROOT}/actions/caches/${cid}"
    )"
    if [ "${code}" != "204" ]; then
      echo "DELETE failed for cache id=${cid} HTTP ${code}" >&2
      exit 1
    fi
  done < <(jq -c '.actions_caches[]' <<<"${json}")

  page=$((page + 1))
done

echo "Summary: matched_stale_non_protected=${pruned} skipped_protected_branch=${skipped_protected} skipped_fresh=${skipped_fresh}"
