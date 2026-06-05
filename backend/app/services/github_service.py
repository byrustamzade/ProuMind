import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx


class GitHubService:
    valid_issue_states = {"open", "closed", "all"}

    def build_issues_source(self, repo_url: str, state: str, limit: int) -> str:
        clean_repo_url = self._clean_repo_url(repo_url)
        return f"{clean_repo_url}?{urlencode({'state': state, 'limit': limit})}"

    def parse_issues_source(
        self,
        source: str,
        state: str | None = None,
        limit: int | None = None,
    ) -> tuple[str, str, int]:
        parsed = urlparse(source)
        query_params = parse_qs(parsed.query)

        source_state = (state or query_params.get("state", ["open"])[0]).lower().strip()
        if source_state not in self.valid_issue_states:
            raise ValueError("State must be one of: open, closed, all.")

        raw_limit = limit if limit is not None else query_params.get("limit", [20])[0]
        try:
            source_limit = int(raw_limit)
        except (TypeError, ValueError) as error:
            raise ValueError("GitHub issues limit must be an integer.") from error

        source_limit = max(1, min(source_limit, 100))

        return self._clean_repo_url(source), source_state, source_limit

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse(self._clean_repo_url(repo_url))

        if parsed.netloc.lower() != "github.com":
            raise ValueError("Only github.com repository URLs are supported.")

        parts = [part for part in parsed.path.strip("/").split("/") if part]

        if len(parts) < 2:
            raise ValueError("Invalid GitHub repository URL.")

        owner = parts[0]
        repo = parts[1].replace(".git", "")

        if not re.match(r"^[A-Za-z0-9_.-]+$", owner):
            raise ValueError("Invalid GitHub owner.")

        if not re.match(r"^[A-Za-z0-9_.-]+$", repo):
            raise ValueError("Invalid GitHub repository name.")

        return owner, repo

    def _clean_repo_url(self, repo_url: str) -> str:
        parsed = urlparse(repo_url)
        clean_path = parsed.path.rstrip("/")
        return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))

    def fetch_issues_text(
        self,
        source: str,
        state: str | None = None,
        limit: int | None = None,
    ) -> tuple[str, str]:
        repo_url, state, limit = self.parse_issues_source(source, state, limit)
        owner, repo = self.parse_repo_url(repo_url)

        query_parts = [f"repo:{owner}/{repo}", "type:issue"]
        if state != "all":
            query_parts.append(f"state:{state}")

        response = httpx.get(
            "https://api.github.com/search/issues",
            params={
                "q": " ".join(query_parts),
                "sort": "updated",
                "order": "desc",
                "per_page": limit,
            },
            timeout=30,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ProuMindBot/0.1",
            },
        )

        response.raise_for_status()
        issues = response.json().get("items", [])
        issue_blocks = []

        for issue in issues:
            issue_blocks.append(
                f"""
Issue #{issue.get("number")}
Title: {issue.get("title")}
State: {issue.get("state")}
Author: {(issue.get("user") or {}).get("login")}
Created At: {issue.get("created_at")}
Updated At: {issue.get("updated_at")}
URL: {issue.get("html_url")}

Body:
{issue.get("body") or ""}
""".strip()
            )

        if not issue_blocks:
            raise ValueError(
                f"No GitHub issues found for {owner}/{repo} with state={state}."
            )

        title = f"GitHub Issues: {owner}/{repo}"

        return title, "\n\n---\n\n".join(issue_blocks)


github_service = GitHubService()
