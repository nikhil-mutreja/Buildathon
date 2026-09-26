"""Request understanding, issue triage, and decision logic for DevPilot."""

import re
import os
import json
import logging
from typing import Any

logger = logging.getLogger("DevPilot.Analyzer")


def parse_user_intent(request: str) -> dict[str, Any]:
    """Parse user natural language prompt into structured intent flags.

    Determines which tools are requested and sets up the execution plan.
    """
    req_lower = request.lower()

    # Determine GitHub intent
    # Default is True for development workflows unless explicitly excluded
    needs_github = any(
        kw in req_lower
        for kw in ["github", "issue", "repo", "repository", "bug", "triage", "analyze"]
    ) or not any(kw in req_lower for kw in ["jira only", "slack only"])

    # Determine Jira intent
    needs_jira = any(
        kw in req_lower
        for kw in ["jira", "task", "ticket", "create task", "create issue", "log bug", "track"]
    )

    # Determine Slack intent
    needs_slack = any(
        kw in req_lower
        for kw in ["slack", "notify", "alert", "message", "team", "inform", "broadcast"]
    )

    # Determine severity focus
    severity_threshold = "CRITICAL"
    if "high" in req_lower:
        severity_threshold = "HIGH"
    elif "all" in req_lower:
        severity_threshold = "ALL"

    selected_tools = []
    plan = ["Understand user request"]
    if needs_github:
        selected_tools.append("github.issue.get1")
        plan.append("Retrieve and analyze repository issues from GitHub")
    if needs_jira:
        selected_tools.append("jira.api.issue.create")
        plan.append("Conditionally create Jira tasks for actionable issues")
    if needs_slack:
        selected_tools.append("slack.chat.postmessage.create")
        plan.append("Conditionally notify development team on Slack")
    plan.append("Synthesize final report and decision audit trail")

    intent = {
        "needs_github": needs_github,
        "needs_jira": needs_jira,
        "needs_slack": needs_slack,
        "severity_threshold": severity_threshold,
        "selected_tools": selected_tools,
        "plan": plan,
    }

    logger.info(
        f"[AGENT] Intent parsed: GitHub={needs_github}, Jira={needs_jira}, Slack={needs_slack}"
    )
    return intent


def triage_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Analyze a single GitHub issue and classify severity with reasoning.

    Uses actual issue attributes (title, body, labels, comments) returned
    by GitHub/Swytchcode without inventing facts.
    """
    title = issue.get("title", "")
    body = issue.get("body") or ""
    number = issue.get("number", 0)
    html_url = issue.get("html_url", "")
    author = issue.get("user", {}).get("login", "unknown") if isinstance(issue.get("user"), dict) else "unknown"

    raw_labels = issue.get("labels", [])
    labels = []
    for l in raw_labels:
        if isinstance(l, dict) and "name" in l:
            labels.append(l["name"].lower())
        elif isinstance(l, str):
            labels.append(l.lower())

    combined_text = f"{title} {body} {' '.join(labels)}".lower()

    # Rule-based heuristic triage (guarantees deterministic, fast, offline-safe classification)
    severity = "LOW"
    reason = "Standard maintenance or minor enhancement task."
    is_actionable = False

    # Check Critical Criteria
    is_security = any(k in combined_text for k in [
        "security", "cve", "vulnerability", "hijack", "exploit", 
        "token bypass", "token leak", "auth leak", "data leak", "credential leak"
    ])
    is_500 = any(k in combined_text for k in ["500", "internal server error", "crash", "panic", "production incident", "p0", "outage"])
    is_payment = any(k in combined_text for k in ["payment", "checkout", "billing", "credit card"])

    if is_security:
        severity = "CRITICAL"
        is_actionable = True
        reason = "Potential security vulnerability or authentication/session exposure affecting production."
    elif is_500 or (is_payment and "fail" in combined_text):
        severity = "CRITICAL"
        is_actionable = True
        reason = "Production-impacting service failure or critical API error affecting business continuity."
    elif any(k in combined_text for k in ["performance", "memory leak", "leak", "deadlock", "hang", "p1", "high"]):
        severity = "HIGH"
        is_actionable = True
        reason = "Severe performance degradation or system resource exhaustion requiring developer attention."
    elif any(k in combined_text for k in ["bug", "defect", "broken", "regression"]):
        severity = "MEDIUM"
        is_actionable = False
        reason = "Functional defect affecting user experience without catastrophic system impact."
    elif any(k in combined_text for k in ["doc", "docs", "documentation", "typo"]):
        severity = "LOW"
        is_actionable = False
        reason = "Documentation improvement or cosmetic fix."
    else:
        severity = "LOW"
        is_actionable = False
        reason = "General feature request or routine enhancement."

    return {
        "id": issue.get("id", number),
        "number": number,
        "title": title,
        "body": body,
        "html_url": html_url,
        "author": author,
        "labels": labels,
        "severity": severity,
        "is_actionable": is_actionable,
        "reason": reason,
        "jira_ticket_key": None,
    }


def should_create_jira(intent: dict[str, Any], actionable_issues: list[dict[str, Any]]) -> tuple[bool, str]:
    """Decide whether Jira task creation should proceed."""
    if not intent.get("needs_jira", False):
        return False, "Jira skipped: task creation was not requested in user prompt."
    if not actionable_issues:
        return False, "Jira skipped: no critical or actionable issues were identified during triage."
    return True, f"Jira selected: {len(actionable_issues)} actionable issue(s) require issue tracking."


def should_send_slack(intent: dict[str, Any], jira_results: list[dict[str, Any]], actionable_issues: list[dict[str, Any]]) -> tuple[bool, str]:
    """Decide whether Slack notification should proceed."""
    if not intent.get("needs_slack", False):
        return False, "Slack skipped: team notification was not requested in user prompt."
    if not jira_results and not actionable_issues:
        return False, "Slack skipped: no actionable updates or tasks to broadcast to the team."
    return True, f"Slack selected: team notification requested for {len(jira_results or actionable_issues)} actionable item(s)."


def format_slack_message(
    jira_results: list[dict[str, Any]],
    actionable_issues: list[dict[str, Any]],
    repo_name: str,
) -> str:
    """Format rich Slack notification dynamically from actual results."""
    count = len(actionable_issues)
    header = f"🚨 *[DevPilot Alert] {count} Actionable Issue{'s' if count != 1 else ''} Identified in `{repo_name}`*"

    lines = [header, ""]
    for issue in actionable_issues:
        num = issue.get("number")
        title = issue.get("title")
        sev = issue.get("severity", "CRITICAL")
        reason = issue.get("reason", "")
        jira_key = issue.get("jira_ticket_key") or "N/A"

        lines.append(f"• *GitHub #{num}*: {title}")
        lines.append(f"   Severity: *{sev}* | Jira Task: `{jira_key}`")
        lines.append(f"   Reason: _{reason}_")
        lines.append("")

    lines.append("⚡ *Action*: Jira tracking tickets generated. Engineers please review.")
    return "\n".join(lines)
