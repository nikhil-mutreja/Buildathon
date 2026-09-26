"""Swytchcode Client: Unified execution layer adapter for GitHub, Jira, and Slack.

Supports both Live Swytchcode execution and high-fidelity Demo/Mock simulation.
Uses exact canonical tool IDs registered in Swytchcode:
- github.issue.get1
- jira.api.issue.create
- slack.chat.postmessage.create
"""

import os
import time
import logging
from typing import Any, Optional

logger = logging.getLogger("DevPilot.Swytchcode")

# Canonical tool IDs as registered in Swytchcode tooling.json
TOOL_GITHUB_ISSUES = "github.issue.get1"
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

    def fetch_github_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch repository issues using Swytchcode github.issue.get1.

        Args:
            owner: Repository owner/organization.
            repo: Repository name.
            state: Issue state ('open', 'closed', 'all').
            per_page: Number of issues to retrieve.

        Returns:
            List of normalized issue dictionaries.
        """
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

    def create_jira_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        priority: str = "High",
        issue_type: str = "Bug",
        github_issue_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a Jira issue using Swytchcode jira.api.issue.create.

        Args:
            project_key: Jira project key (e.g. 'DEV').
            summary: Short title of the task.
            description: Detailed description of the task.
            priority: Priority name (e.g. 'Highest', 'High', 'Medium').
            issue_type: Type of issue (e.g. 'Bug', 'Task').
            github_issue_number: Associated GitHub issue number for traceability.

        Returns:
            Created issue details including key, id, and summary.
        """
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Jira issue creation in {project_key}")
            return self._mock_jira_issue(project_key, summary, priority, issue_type, github_issue_number)

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

    def send_slack_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Send a notification using Swytchcode slack.chat.postmessage.create.

        Args:
            channel: Target Slack channel or conversation ID.
            text: Fallback/plain message text.
            blocks: Optional Slack Block Kit layout array.

        Returns:
            Delivery result status.
        """
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
                    "during OAuth callback redirections. This exposes authenticated accounts "
                    "to unauthorized session hijacking in shared log aggregators."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/101",
                "user": {"login": "sec-auditor"},
                "labels": [{"name": "security"}, {"name": "critical"}, {"name": "cve"}],
                "state": "open",
                "comments": 4,
                "created_at": "2026-09-25T14:20:00Z",
                "updated_at": "2026-09-26T08:15:00Z",
            },
            {
                "id": 1002,
                "number": 102,
                "title": "[BUG] Payment API returns HTTP 500 on international credit card checkouts",
                "body": (
                    "Production incident: The payment processing gateway fails with an "
                    "unhandled 500 Internal Server Error when processing non-USD currencies. "
                    "Root cause appears to be a decimal precision conversion fault in the payment service."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/102",
                "user": {"login": "ops-lead"},
                "labels": [{"name": "bug"}, {"name": "p0"}, {"name": "payments"}],
                "state": "open",
                "comments": 12,
                "created_at": "2026-09-25T18:45:00Z",
                "updated_at": "2026-09-26T07:30:00Z",
            },
            {
                "id": 1003,
                "number": 103,
                "title": "[PERF] High memory consumption in WebSocket connection pool",
                "body": (
                    "Under sustained load of >5,000 concurrent client connections, the "
                    "real-time event broker leaks file descriptors and socket buffers. "
                    "Workaround requires restarting worker pods every 6 hours."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/103",
                "user": {"login": "perf-eng"},
                "labels": [{"name": "performance"}, {"name": "backend"}],
                "state": "open",
                "comments": 3,
                "created_at": "2026-09-24T11:10:00Z",
                "updated_at": "2026-09-25T16:00:00Z",
            },
            {
                "id": 1004,
                "number": 104,
                "title": "[DOCS] Update API setup guide for Python 3.12 compatibility",
                "body": (
                    "The local setup guide still mentions python 3.10 and has an outdated "
                    "dependency reference for virtualenv activation."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/104",
                "user": {"login": "contributor-42"},
                "labels": [{"name": "documentation"}, {"name": "good-first-issue"}],
                "state": "open",
                "comments": 1,
                "created_at": "2026-09-23T09:00:00Z",
                "updated_at": "2026-09-23T10:00:00Z",
            },
            {
                "id": 1005,
                "number": 105,
                "title": "[FEATURE] Add dark mode theme switcher to settings panel",
                "body": (
                    "Users have requested a toggle between Light, Dark, and System theme "
                    "in the main dashboard settings."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/105",
                "user": {"login": "designer-amy"},
                "labels": [{"name": "enhancement"}, {"name": "frontend"}],
                "state": "open",
                "comments": 2,
                "created_at": "2026-09-22T15:30:00Z",
                "updated_at": "2026-09-24T12:00:00Z",
            },
        ]

    def _mock_jira_issue(
        self,
        project_key: str,
        summary: str,
        priority: str,
        issue_type: str,
        github_issue_number: Optional[int],
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
            "status": "Created",
            "url": f"https://mock-company.atlassian.net/browse/{key}",
            "github_issue_number": issue_num,
        }

    def _mock_slack_message(self, channel: str, text: str) -> dict[str, Any]:
        """Realistic mock Slack postMessage response."""
        return {
            "ok": True,
            "channel": channel,
            "ts": f"{int(time.time())}.012400",
            "message": {
                "text": text,
                "username": "DevPilot-Bot",
                "bot_id": "B08SWYTCH01",
                "type": "message",
            },
        }
