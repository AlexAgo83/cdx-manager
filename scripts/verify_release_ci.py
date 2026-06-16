#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_WORKFLOW = "ci.yml"


class GitHubApi:
    def __init__(self, api_url, repo, token):
        self.api_url = api_url.rstrip("/")
        self.repo = repo
        self.token = token

    def get(self, path, params=None):
        url = f"{self.api_url}/repos/{self.repo}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "cdx-manager-release-ci-check",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API request failed: {error.code} {url}: {detail}") from error


def normalize_tag(tag):
    tag = str(tag or "").strip()
    if not tag:
        raise ValueError("release tag is required")
    return tag if tag.startswith("v") else f"v{tag}"


def resolve_tag_commit(api, tag):
    tag = normalize_tag(tag)
    ref = api.get(f"/git/ref/tags/{tag}")
    obj = ref.get("object") or {}

    for _ in range(5):
        obj_type = obj.get("type")
        obj_sha = obj.get("sha")
        if obj_type == "commit" and obj_sha:
            return obj_sha
        if obj_type == "tag" and obj_sha:
            tag_obj = api.get(f"/git/tags/{obj_sha}")
            obj = tag_obj.get("object") or {}
            continue
        raise ValueError(f"tag {tag} does not resolve to a commit")

    raise ValueError(f"tag {tag} is nested too deeply to resolve")


def _runs_for_commit(api, workflow, commit_sha):
    payload = api.get(
        f"/actions/workflows/{workflow}/runs",
        params={"head_sha": commit_sha, "per_page": 50},
    )
    runs = payload.get("workflow_runs") or []
    return [run for run in runs if run.get("head_sha") == commit_sha]


def verify_ci_success(api, tag, workflow=DEFAULT_WORKFLOW, timeout=600, interval=15, output=sys.stdout):
    tag = normalize_tag(tag)
    commit_sha = resolve_tag_commit(api, tag)
    deadline = time.monotonic() + max(0, timeout)
    last_state = "no runs found"

    while True:
        runs = _runs_for_commit(api, workflow, commit_sha)
        successful = [
            run for run in runs if run.get("status") == "completed" and run.get("conclusion") == "success"
        ]
        if successful:
            run = sorted(successful, key=lambda item: item.get("created_at") or "", reverse=True)[0]
            print(
                f"Release CI validation OK for {tag} ({commit_sha}) via run {run.get('html_url') or run.get('id')}",
                file=output,
            )
            return commit_sha

        if runs:
            last_state = ", ".join(
                f"{run.get('status') or 'unknown'}/{run.get('conclusion') or 'pending'}"
                for run in runs[:5]
            )

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"CI workflow {workflow} is not successful for {tag} ({commit_sha}); latest state: {last_state}"
            )

        print(
            f"Waiting for CI workflow {workflow} to pass for {tag} ({commit_sha}); latest state: {last_state}",
            file=output,
        )
        time.sleep(max(1, interval))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Block registry publication until the release tag's commit has a successful CI run."
    )
    parser.add_argument("--tag", required=True, help="Release tag to validate, for example v0.9.2")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow file or ID to check")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds to wait for a successful run")
    parser.add_argument("--interval", type=int, default=15, help="Seconds between polling attempts")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="Repository in owner/name form")
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args(argv)

    if not args.repo:
        raise SystemExit("Release CI validation failed: --repo or GITHUB_REPOSITORY is required")

    api = GitHubApi(args.api_url, args.repo, args.token)
    try:
        verify_ci_success(
            api,
            args.tag,
            workflow=args.workflow,
            timeout=args.timeout,
            interval=args.interval,
        )
    except (RuntimeError, TimeoutError, ValueError) as error:
        raise SystemExit(f"Release CI validation failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
