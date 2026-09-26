"""State definitions for DevPilot LangGraph Agent."""
from typing import TypedDict, Any, Optional
from pydantic import BaseModel, Field


class AnalyzedIssue(BaseModel):
    """Structured representation of a triaged GitHub issue."""
    id: int
    number: int
    title: str
    body: str = ""
    html_url: str = ""
    author: str = ""
    labels: list[str] = Field(default_factory=list)
    severity: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    is_actionable: bool = False
    reason: str = ""
    jira_ticket_key: Optional[str] = None


class JiraTicketResult(BaseModel):
    """Result of Jira issue creation."""
    key: str
    summary: str
    issue_type: str = "Bug"
    priority: str = "High"
    github_issue_number: int
    url: str = ""
    status: str = "Created"


class SlackNotificationResult(BaseModel):
    """Result of Slack notification delivery."""
    channel: str
    ts: str = ""
    summary: str
    delivered: bool = True
    message_text: str = ""


class DevPilotState(TypedDict, total=False):
    """LangGraph state schema for DevPilot workflow."""
    user_request: str
    intent: dict[str, Any]
    plan: list[str]
    selected_tools: list[str]
    repo_owner: str
    repo_name: str
    jira_project: str
    slack_channel: str
    app_mode: str  # 'real' or 'mock'
    github_results: list[dict[str, Any]]
    analyzed_issues: list[dict[str, Any]]
    actionable_issues: list[dict[str, Any]]
    jira_results: list[dict[str, Any]]
    slack_results: list[dict[str, Any]]
    actions_taken: list[str]
    decisions: list[str]
    errors: list[str]
    final_response: str
