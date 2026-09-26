"""LangGraph workflow graph for DevPilot: Autonomous AI Software Engineering Agent."""

import os
import logging
from typing import Any
from langgraph.graph import StateGraph, START, END

from app.agent.state import DevPilotState
from app.agent.analyzer import (
    parse_user_intent,
    triage_issue,
    should_create_jira,
    should_send_slack,
    format_slack_message,
)
from app.integrations.swytchcode_client import SwytchcodeClient

logger = logging.getLogger("DevPilot.Graph")


# =============================================================================
# Graph Node Definitions
# =============================================================================

def understand_request_node(state: DevPilotState) -> dict[str, Any]:
    """Parse user natural language prompt and determine intent and tools."""
    user_request = state.get("user_request", "")
    logger.info(f"[AGENT] Processing user request: '{user_request}'")

    intent = parse_user_intent(user_request)
    selected_tools = intent.get("selected_tools", [])
    plan = intent.get("plan", [])

    decisions = state.get("decisions", [])
    decisions.append(
        f"Intent analyzed: GitHub={intent['needs_github']}, "
        f"Jira={intent['needs_jira']}, Slack={intent['needs_slack']}."
    )

    actions = state.get("actions_taken", [])
    actions.append(f"Request understood. Selected {len(selected_tools)} Swytchcode tool(s): {', '.join(selected_tools) or 'None'}")

    return {
        "intent": intent,
        "selected_tools": selected_tools,
        "plan": plan,
        "decisions": decisions,
        "actions_taken": actions,
    }


def fetch_github_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode github.issue.get1 to list repository issues."""
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])

    decisions.append(f"GitHub selected: fetching issues for repository `{owner}/{repo}`.")

    try:
        issues = client.fetch_github_issues(owner=owner, repo=repo)
        actions.append(f"GitHub issues retrieved: {len(issues)} open issue(s) fetched via Swytchcode.")
        return {
            "github_results": issues,
            "decisions": decisions,
            "actions_taken": actions,
            "errors": errors,
        }
    except Exception as e:
        err_msg = f"GitHub API error: {str(e)}"
        logger.error(err_msg)
        errors.append(err_msg)
        actions.append("GitHub issue retrieval failed.")
        return {
            "github_results": [],
            "decisions": decisions,
            "actions_taken": actions,
            "errors": errors,
        }


def analyze_issues_node(state: DevPilotState) -> dict[str, Any]:
    """Triage and classify all retrieved GitHub issues into severities."""
    raw_issues = state.get("github_results", [])
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    analyzed = []
    actionable = []

    for issue in raw_issues:
        result = triage_issue(issue)
        analyzed.append(result)
        if result["is_actionable"]:
            actionable.append(result)

    decisions.append(
        f"Issue triage complete: {len(analyzed)} issue(s) inspected, "
        f"{len(actionable)} actionable (CRITICAL/HIGH) issue(s) identified."
    )
    actions.append(f"Analyzed {len(analyzed)} issues: identified {len(actionable)} actionable items.")

    return {
        "analyzed_issues": analyzed,
        "actionable_issues": actionable,
        "decisions": decisions,
        "actions_taken": actions,
    }


def create_jira_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode jira.api.issue.create for all actionable issues."""
    actionable = state.get("actionable_issues", [])
    project_key = state.get("jira_project") or os.getenv("JIRA_PROJECT_KEY", "DEV")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    jira_results = []

    decisions.append(f"Jira selected: creating tasks in project `{project_key}` for {len(actionable)} actionable issue(s).")

    for issue in actionable:
        issue_num = issue["number"]
        summary = f"[GH-{issue_num}] {issue['title']}"
        desc = (
            f"Automated task created by DevPilot Agent for GitHub Issue #{issue_num}.\n\n"
            f"Severity: {issue['severity']}\n"
            f"Triage Assessment: {issue['reason']}\n"
            f"GitHub Link: {issue['html_url']}\n\n"
            f"Description:\n{issue.get('body', '')}"
        )
        priority = "Highest" if issue["severity"] == "CRITICAL" else "High"

        try:
            res = client.create_jira_issue(
                project_key=project_key,
                summary=summary,
                description=desc,
                priority=priority,
                issue_type="Bug",
                github_issue_number=issue_num,
            )
            ticket_key = res.get("key", f"{project_key}-{issue_num}")
            issue["jira_ticket_key"] = ticket_key
            jira_results.append(res)
            actions.append(f"Jira task created: `{ticket_key}` for GitHub #{issue_num}.")
        except Exception as e:
            err_msg = f"Failed to create Jira task for GitHub #{issue_num}: {str(e)}"
            logger.error(err_msg)
            errors.append(err_msg)

    return {
        "actionable_issues": actionable,
        "jira_results": jira_results,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def send_slack_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode slack.chat.postmessage.create to notify the team."""
    channel = state.get("slack_channel") or os.getenv("SLACK_CHANNEL", "#dev-alerts")
    repo_name = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    actionable = state.get("actionable_issues", [])
    jira_results = state.get("jira_results", [])
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    slack_results = []

    decisions.append(f"Slack selected: notifying channel `{channel}` of {len(actionable)} actionable update(s).")
    message_text = format_slack_message(jira_results, actionable, repo_name)

    try:
        res = client.send_slack_message(channel=channel, text=message_text)
        slack_results.append(res)
        actions.append(f"Slack notification dispatched to channel `{channel}`.")
    except Exception as e:
        err_msg = f"Failed to send Slack message: {str(e)}"
        logger.error(err_msg)
        errors.append(err_msg)

    return {
        "slack_results": slack_results,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def synthesize_response_node(state: DevPilotState) -> dict[str, Any]:
    """Synthesize complete final summary, traceability matrix, and audit trail."""
    user_request = state.get("user_request", "")
    analyzed = state.get("analyzed_issues", [])
    actionable = state.get("actionable_issues", [])
    jira_results = state.get("jira_results", [])
    slack_results = state.get("slack_results", [])
    errors = state.get("errors", [])
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    lines = []
    lines.append(f"### DevPilot Agent Execution Report")
    lines.append(f"**User Request:** \"{user_request}\"\n")

    # High-level outcome
    lines.append("#### Executive Summary")
    lines.append(f"- **Issues Triaged:** {len(analyzed)}")
    lines.append(f"- **Actionable Issues Found:** {len(actionable)}")
    lines.append(f"- **Jira Tasks Created:** {len(jira_results)}")
    lines.append(f"- **Slack Notifications Dispatched:** {len(slack_results)}")

    if errors:
        lines.append("\n#### ⚠️ Errors / Warnings Encountered")
        for err in errors:
            lines.append(f"- {err}")

    # Traceability Matrix
    if actionable:
        lines.append("\n#### 🔗 Source-to-Action Traceability")
        lines.append("| GitHub Issue | Severity | Triage Assessment | Jira Task | Slack Alert |")
        lines.append("| :--- | :---: | :--- | :---: | :---: |")
        for item in actionable:
            gh_link = f"#{item['number']}"
            sev = item["severity"]
            reason = item["reason"]
            jira_key = item.get("jira_ticket_key") or "N/A"
            slack_status = "Dispatched" if slack_results else "N/A"
            lines.append(f"| {gh_link} | **{sev}** | {reason} | `{jira_key}` | {slack_status} |")

    # Decisions & Actions
    lines.append("\n#### 📋 Agent Decision & Action Audit Trail")
    for d in decisions:
        lines.append(f"- **[DECISION]** {d}")
    for a in actions:
        lines.append(f"- **[ACTION]** {a}")

    final_resp = "\n".join(lines)
    return {"final_response": final_resp}


# =============================================================================
# Conditional Edge Routing Functions
# =============================================================================

def route_after_understand(state: DevPilotState) -> str:
    """Route to fetch_github if repository issues are needed, else synthesize."""
    intent = state.get("intent", {})
    if intent.get("needs_github", True):
        return "fetch_github"
    return "synthesize_response"


def route_after_analyze(state: DevPilotState) -> str:
    """Conditionally route after issue triage based on user intent and actionable issues."""
    intent = state.get("intent", {})
    actionable = state.get("actionable_issues", [])
    decisions = state.get("decisions", [])

    should_jira, reason_jira = should_create_jira(intent, actionable)
    if should_jira:
        return "create_jira"

    decisions.append(reason_jira)

    # If Jira is skipped, check if Slack is requested
    should_slack, reason_slack = should_send_slack(intent, [], actionable)
    if should_slack:
        return "send_slack"

    decisions.append(reason_slack)
    return "synthesize_response"


def route_after_jira(state: DevPilotState) -> str:
    """Conditionally route after Jira task creation to Slack or final response."""
    intent = state.get("intent", {})
    jira_results = state.get("jira_results", [])
    actionable = state.get("actionable_issues", [])
    decisions = state.get("decisions", [])

    should_slack, reason_slack = should_send_slack(intent, jira_results, actionable)
    if should_slack:
        return "send_slack"

    decisions.append(reason_slack)
    return "synthesize_response"


# =============================================================================
# Graph Construction
# =============================================================================

def build_devpilot_graph():
    """Build and compile the LangGraph StateGraph workflow."""
    workflow = StateGraph(DevPilotState)

    # Add Nodes
    workflow.add_node("understand_request", understand_request_node)
    workflow.add_node("fetch_github", fetch_github_node)
    workflow.add_node("analyze_issues", analyze_issues_node)
    workflow.add_node("create_jira", create_jira_node)
    workflow.add_node("send_slack", send_slack_node)
    workflow.add_node("synthesize_response", synthesize_response_node)

    # Add Edges
    workflow.add_edge(START, "understand_request")

    workflow.add_conditional_edges(
        "understand_request",
        route_after_understand,
        {
            "fetch_github": "fetch_github",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_edge("fetch_github", "analyze_issues")

    workflow.add_conditional_edges(
        "analyze_issues",
        route_after_analyze,
        {
            "create_jira": "create_jira",
            "send_slack": "send_slack",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_conditional_edges(
        "create_jira",
        route_after_jira,
        {
            "send_slack": "send_slack",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_edge("send_slack", "synthesize_response")
    workflow.add_edge("synthesize_response", END)

    return workflow.compile()


def run_devpilot_agent(
    user_request: str,
    repo_owner: str = "octocat",
    repo_name: str = "Hello-World",
    jira_project: str = "DEV",
    slack_channel: str = "#dev-alerts",
    app_mode: str = "mock",
) -> DevPilotState:
    """Execute the complete DevPilot LangGraph workflow.

    Args:
        user_request: Natural language query from developer.
        repo_owner: GitHub repository owner.
        repo_name: GitHub repository name.
        jira_project: Jira project key.
        slack_channel: Slack notification channel.
        app_mode: 'real' (live Swytchcode) or 'mock' (demo simulation).

    Returns:
        Final DevPilotState containing all intermediate results, decisions, and output.
    """
    app = build_devpilot_graph()

    initial_state: DevPilotState = {
        "user_request": user_request,
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "jira_project": jira_project,
        "slack_channel": slack_channel,
        "app_mode": app_mode,
        "selected_tools": [],
        "plan": [],
        "github_results": [],
        "analyzed_issues": [],
        "actionable_issues": [],
        "jira_results": [],
        "slack_results": [],
        "actions_taken": [],
        "decisions": [],
        "errors": [],
        "final_response": "",
    }

    final_state = app.invoke(initial_state)
    return final_state
