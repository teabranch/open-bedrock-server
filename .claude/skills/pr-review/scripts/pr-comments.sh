#!/usr/bin/env bash
set -euo pipefail

# Fetch and display all review comments on a PR.
# Usage: pr-comments.sh [--repo OWNER/REPO] PR_NUMBER

REPO=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) REPO="$2"; shift 2 ;;
        *) break ;;
    esac
done

PR_NUMBER="${1:?Usage: pr-comments.sh [--repo OWNER/REPO] PR_NUMBER}"

if [[ -z "$REPO" ]]; then
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
fi

# Fetch thread resolution status via GraphQL
THREADS_JSON=$(gh api graphql -f query="
{
  repository(owner: \"${REPO%%/*}\", name: \"${REPO##*/}\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { databaseId }
          }
        }
      }
    }
  }
}" --jq '.data.repository.pullRequest.reviewThreads.nodes')

# Build a map of comment_id -> {thread_id, resolved}
THREAD_MAP=$(echo "$THREADS_JSON" | jq -r '
  [.[] | {
    comment_id: .comments.nodes[0].databaseId,
    thread_id: .id,
    resolved: .isResolved
  }]
')

# Fetch all review comments via REST
COMMENTS=$(gh api "repos/$REPO/pulls/$PR_NUMBER/comments" --paginate)

# Display formatted output
echo "$COMMENTS" | jq -r --argjson threads "$THREAD_MAP" '
  .[] | . as $c |
  ($threads | map(select(.comment_id == $c.id)) | first // {resolved: "unknown", thread_id: "?"}) as $t |
  "──────────────────────────────────────────────────",
  "ID: \($c.id)  |  Thread: \(if $t.resolved == true then "RESOLVED" elif $t.resolved == false then "UNRESOLVED" else "?" end)  |  Reply-to: \($c.in_reply_to_id // "none")",
  "File: \($c.path):\($c.original_line // $c.line // "?")",
  "Thread ID: \($t.thread_id)",
  "",
  ($c.body | split("\n") | if length > 10 then .[:10] + ["... (truncated)"] else . end | join("\n")),
  ""
'
