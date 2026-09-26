"""Swytchcode Client: Unified execution layer adapter for GitHub, Jira, and Slack.

Supports both Live Swytchcode execution and high-fidelity Demo/Mock simulation.
Uses exact canonical tool IDs registered in Swytchcode:
- github.issue.get1
- github.content.get
- github.content.update
- github.pull.create
- jira.api.issue.create
- slack.chat.postmessage.create
"""

import os
import time
import base64
import logging
from typing import Any, Optional

logger = logging.getLogger("DevPilot.Swytchcode")

# Canonical tool IDs as registered in Swytchcode tooling.json
TOOL_GITHUB_ISSUES = "github.issue.get1"
TOOL_GITHUB_CONTENT_GET = "github.content.get"
TOOL_GITHUB_CONTENT_UPDATE = "github.content.update"
TOOL_GITHUB_PULL_CREATE = "github.pull.create"
TOOL_JIRA_CREATE_ISSUE = "jira.api.issue.create"
TOOL_SLACK_POST_MESSAGE = "slack.chat.postmessage.create"


class SwytchcodeClient:
    """Interface to Swytchcode Execution Authority for agent tools."""

    def __init__(self, mode: Optional[str] = None):
        """Initialize client with mode ('real' or 'mock').

        Defaults to environment variable APP_MODE, falling back to 'mock' if
        credentials are not configured.
        """
        env_mode = os.getenv("APP_MODE", "").lower()
        if mode:
            self.mode = mode.lower()
        elif env_mode in ("real", "production"):
            self.mode = "real"
        else:
            self.mode = "mock"

        self._swx = None
        if self.mode == "real":
            try:
                from swytchcode_runtime import Swytchcode
                self._swx = Swytchcode()
            except ImportError:
                logger.warning("swytchcode_runtime not found; falling back to mock mode.")
                self.mode = "mock"

    def is_mock(self) -> bool:
        """Return True if running in Mock/Demo mode."""
        return self.mode == "mock"

    # =========================================================================
    # GitHub Repository Tools
    # =========================================================================

    def fetch_github_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch repository issues using Swytchcode github.issue.get1."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating GitHub issues for {owner}/{repo}")
            return self._mock_github_issues(owner, repo)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_ISSUES} for {owner}/{repo}")
        token = os.getenv("GITHUB_TOKEN")
        args: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "state": state,
            "per_page": per_page,
        }
        if token:
            args["Authorization"] = f"Bearer {token}"

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_ISSUES, args)
            if isinstance(result, list):
                logger.info(f"[TOOL] GitHub returned {len(result)} issues via Swytchcode")
                return result
            elif isinstance(result, dict) and "items" in result:
                return result["items"]
            elif isinstance(result, dict) and "error" in result:
                raise RuntimeError(result.get("error", "Unknown Swytchcode error"))
            return [result] if result else []
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub error: {err_msg}")

    def get_repository_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> dict[str, Any]:
        """Fetch file contents from repository using Swytchcode github.content.get."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating repository file read for {path}")
            return self._mock_repository_file(path)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_CONTENT_GET} for {path}")
        token = os.getenv("GITHUB_TOKEN")
        args: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "path": path,
            "ref": ref,
        }
        if token:
            args["Authorization"] = f"Bearer {token}"

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_CONTENT_GET, args)
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub content get failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub content get error: {err_msg}")

    def update_repository_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> dict[str, Any]:
        """Commit file change to repository using Swytchcode github.content.update."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating repository file commit to branch {branch} for {path}")
            return {
                "content": {"path": path, "sha": "mock-sha-commit-9921"},
                "commit": {"message": message, "sha": "mock-commit-sha-4921"},
            }

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_CONTENT_UPDATE} on {path}")
        token = os.getenv("GITHUB_TOKEN")
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        args: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "path": path,
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            args["sha"] = sha
        if token:
            args["Authorization"] = f"Bearer {token}"

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_CONTENT_UPDATE, args)
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub file update failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub file update error: {err_msg}")

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
    ) -> dict[str, Any]:
        """Create a pull request in repository using Swytchcode github.pull.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Pull Request creation: {title} ({head} -> {base})")
            return self._mock_pull_request(owner, repo, title, head, base, body)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_PULL_CREATE}: {title}")
        token = os.getenv("GITHUB_TOKEN")
        args: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "title": title,
            "head": head,
            "base": base,
            "body": body,
        }
        if token:
            args["Authorization"] = f"Bearer {token}"

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_PULL_CREATE, args)
            logger.info(f"[TOOL] GitHub PR created via Swytchcode: #{result.get('number', 'OK')}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub PR creation failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub PR creation error: {err_msg}")

    # =========================================================================
    # Jira Task Tracking Tools
    # =========================================================================

    def create_jira_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        priority: str = "High",
        issue_type: str = "Bug",
        github_issue_number: Optional[int] = None,
        pull_request_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a Jira issue using Swytchcode jira.api.issue.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Jira issue creation in {project_key}")
            return self._mock_jira_issue(
                project_key, summary, priority, issue_type, github_issue_number, pull_request_number
            )

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_JIRA_CREATE_ISSUE} in {project_key}")
        args: dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }
        }

        try:
            result = self._swx.tools.execute(TOOL_JIRA_CREATE_ISSUE, args)
            logger.info(f"[TOOL] Jira task created via Swytchcode: {result.get('key', 'OK')}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode Jira execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode Jira error: {err_msg}")

    # =========================================================================
    # Slack Communication Tools
    # =========================================================================

    def send_slack_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Send a notification using Swytchcode slack.chat.postmessage.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Slack notification to {channel}")
            return self._mock_slack_message(channel, text)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_SLACK_POST_MESSAGE} to {channel}")
        body: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }
        if blocks:
            body["blocks"] = blocks

        token = os.getenv("SLACK_BOT_TOKEN")
        args: dict[str, Any] = {"body": body}
        if token:
            args["Authorization"] = f"Bearer {token}"

        try:
            result = self._swx.tools.execute(TOOL_SLACK_POST_MESSAGE, args)
            logger.info(f"[TOOL] Slack notification delivered via Swytchcode to {channel}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode Slack execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode Slack error: {err_msg}")

    # =========================================================================
    # Mock / Demo Implementations
    # =========================================================================

    def _mock_github_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """High-fidelity mock issues matching Swytchcode output schema."""
        return [
            {
                "id": 1001,
                "number": 101,
                "title": "[SECURITY] Remote authentication token leakage in OAuth callback",
                "body": (
                    "CRITICAL: User session tokens are inadvertently logged in plain text "
                    "during OAuth callback redirections in src/auth/oauth_handler.py. This exposes authenticated accounts "
                    "to unauthorized session hijacking in shared log aggregators."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/101",
                "user": {"login": "sec-auditor"},
                "labels": [{"name": "security"}, {"name": "critical"}, {"name": "cve"}],
                "state": "open",
                "comments": 4,
                "file_path": "src/auth/oauth_handler.py",
                "created_at": "2026-09-25T14:20:00Z",
                "updated_at": "2026-09-26T08:15:00Z",
            },
            {
                "id": 1002,
                "number": 102,
                "title": "[BUG] Payment API returns HTTP 500 on international credit card checkouts",
                "body": (
                    "Production incident: The payment processing gateway in src/services/payment_service.py fails with an "
                    "unhandled 500 Internal Server Error when processing non-USD currencies. "
                    "Root cause is floating point division precision without Decimal conversion."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/102",
                "user": {"login": "ops-lead"},
                "labels": [{"name": "bug"}, {"name": "p0"}, {"name": "payments"}],
                "state": "open",
                "comments": 12,
                "file_path": "src/services/payment_service.py",
                "created_at": "2026-09-25T18:45:00Z",
                "updated_at": "2026-09-26T07:30:00Z",
            },
            {
                "id": 1003,
                "number": 103,
                "title": "[PERF] High memory consumption in WebSocket connection pool",
                "body": (
                    "Under sustained load of >5,000 concurrent client connections, the "
                    "real-time event broker in src/realtime/broker.py leaks file descriptors."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/103",
                "user": {"login": "perf-eng"},
                "labels": [{"name": "performance"}, {"name": "backend"}],
                "state": "open",
                "comments": 3,
                "file_path": "src/realtime/broker.py",
                "created_at": "2026-09-24T11:10:00Z",
                "updated_at": "2026-09-25T16:00:00Z",
            },
            {
                "id": 1004,
                "number": 104,
                "title": "[DOCS] Update API setup guide for Python 3.12 compatibility",
                "body": (
                    "The local setup guide in docs/setup.md mentions python 3.10 and has an outdated reference."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/104",
                "user": {"login": "contributor-42"},
                "labels": [{"name": "documentation"}, {"name": "good-first-issue"}],
                "state": "open",
                "comments": 1,
                "file_path": "docs/setup.md",
                "created_at": "2026-09-23T09:00:00Z",
                "updated_at": "2026-09-23T10:00:00Z",
            },
            {
                "id": 1005,
                "number": 105,
                "title": "[FEATURE] Add dark mode theme switcher to settings panel",
                "body": (
                    "Users have requested a toggle between Light, Dark, and System theme "
                    "in src/components/ThemeToggle.tsx."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/105",
                "user": {"login": "designer-amy"},
                "labels": [{"name": "enhancement"}, {"name": "frontend"}],
                "state": "open",
                "comments": 2,
                "file_path": "src/components/ThemeToggle.tsx",
                "created_at": "2026-09-22T15:30:00Z",
                "updated_at": "2026-09-24T12:00:00Z",
            },
        ]

    def _mock_repository_file(self, path: str) -> dict[str, Any]:
        """Realistic codebase files for inspection and debugging."""
        codebase = {
            "src/services/payment_service.py": (
                "# Payment Processing Gateway Service\n"
                "from decimal import Decimal\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def process_transaction(amount, currency, exchange_rate):\n"
                "    # BUGGY CODE: causes float precision crash on non-USD\n"
                "    converted = float(amount) / exchange_rate\n"
                "    if converted <= 0:\n"
                "        raise ValueError('Invalid transaction amount')\n"
                "    # Charge credit card gateway\n"
                "    return {'status': 'processed', 'amount': converted, 'currency': currency}\n"
            ),
            "src/auth/oauth_handler.py": (
                "# OAuth Authentication Callback Handler\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def handle_oauth_callback(auth_code, token_response):\n"
                "    # SECURITY VULNERABILITY: Raw access token logged to shared aggregator\n"
                "    access_token = token_response.get('access_token')\n"
                "    logger.info(f'OAuth callback successful! Token: {access_token}')\n"
                "    return {'authenticated': True, 'token': access_token}\n"
            ),
            "src/components/ThemeToggle.tsx": (
                "// Theme Switcher Component\n"
                "import React, { useState } from 'react';\n\n"
                "export const ThemeToggle = () => {\n"
                "  const [theme, setTheme] = useState('light');\n"
                "  return <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>Toggle Theme</button>;\n"
                "};\n"
            ),
        }
        content = codebase.get(
            path,
            f"# Source file: {path}\n# Module placeholder\ndef handler():\n    return True\n"
        )
        return {
            "name": os.path.basename(path),
            "path": path,
            "sha": "mock-sha-blob-8831",
            "size": len(content),
            "type": "file",
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "encoding": "base64",
            "raw_text": content,
        }

    def _mock_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str
    ) -> dict[str, Any]:
        """Realistic mock GitHub Pull Request creation."""
        pr_number = int(time.time() % 900) + 10
        return {
            "id": 80000 + pr_number,
            "number": pr_number,
            "title": title,
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            "state": "open",
            "head": {"ref": head, "label": f"{owner}:{head}"},
            "base": {"ref": base, "label": f"{owner}:{base}"},
            "body": body,
            "created_at": "2026-09-26T09:59:00Z",
        }

    def _mock_jira_issue(
        self,
        project_key: str,
        summary: str,
        priority: str,
        issue_type: str,
        github_issue_number: Optional[int],
        pull_request_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Realistic mock Jira issue creation response."""
        issue_num = github_issue_number or int(time.time() % 1000)
        key = f"{project_key}-{100 + issue_num}"
        return {
            "id": str(20000 + issue_num),
            "key": key,
            "self": f"https://mock-company.atlassian.net/rest/api/3/issue/{key}",
            "summary": summary,
            "priority": priority,
            "issue_type": issue_type,
            "status": "In Progress" if pull_request_number else "Created",
            "url": f"https://mock-company.atlassian.net/browse/{key}",
            "github_issue_number": issue_num,
            "pull_request_number": pull_request_number,
        }

    def _mock_slack_message(self, channel: str, text: str) -> dict[str, Any]:
        """Realistic mock Slack postMessage response."""
        return {
            "ok": True,
            "channel": channel,
            "ts": f"{int(time.time())}.012400",
            "message": {
                "text": text,
                "username": "DevPilot-AI-Engineer",
                "bot_id": "B08SWYTCH01",
                "type": "message",
            },
        }
