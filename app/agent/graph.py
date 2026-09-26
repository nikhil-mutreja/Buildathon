"""LangGraph workflow graph for DevPilot: Autonomous AI Software Engineering Agent."""

import os
import base64
import logging
from typing import Any
from langgraph.graph import StateGraph, START, END

from app.agent.state import DevPilotState
from app.agent.analyzer import (
    parse_user_intent,
    triage_issue,
    scan_code_for_defects,
    diagnose_and_generate_patch,
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
    """Parse user natural language prompt and determine task type and tools."""
    user_request = state.get("user_request", "")
    logger.info(f"[AGENT] Processing software engineering request: '{user_request}'")

    intent = parse_user_intent(user_request)
    selected_tools = intent.get("selected_tools", [])
    plan = intent.get("plan", [])
    task_type = intent.get("task_type", "issue_triage")

    repo_owner = intent.get("target_repo_owner") or state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo_name = intent.get("target_repo_name") or state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")

    decisions = state.get("decisions", [])
    if intent.get("target_repo_owner") and intent.get("target_repo_name"):
        decisions.append(f"Target public repository identified from request: `{repo_owner}/{repo_name}`.")

    decisions.append(
        f"Task categorized as `{task_type}`. Intent: GitHub={intent['needs_github']}, "
        f"CodeFix={intent['needs_code_fix']}, PR={intent['needs_pr']}, "
        f"Jira={intent['needs_jira']}, Slack={intent['needs_slack']}."
    )

    actions = state.get("actions_taken", [])
    actions.append(f"Request understood: '{task_type}' task initialized for `{repo_owner}/{repo_name}` with {len(selected_tools)} Swytchcode tools.")

    return {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "task_type": task_type,
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
    """Triage repository issues and proactively scan codebase files for bugs."""
    raw_issues = state.get("github_results", [])
    intent = state.get("intent", {})
    target_num = intent.get("target_issue_number")
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    analyzed = []
    actionable = []

    # 1. Triage existing GitHub issues if present
    for issue in raw_issues:
        result = triage_issue(issue)
        # If user targeted a specific issue, prioritize it
        if target_num and result["number"] == target_num:
            result["is_actionable"] = True
        analyzed.append(result)
        if result["is_actionable"]:
            actionable.append(result)

    # Filter to target issue if specifically asked
    if target_num:
        filtered = [i for i in actionable if i["number"] == target_num]
        if filtered:
            actionable = filtered

    # 2. Autonomous Code Defect Scan: If no issues or if user requested finding bugs in repo
    if not actionable or (intent.get("needs_code_fix", False) and not target_num):
        decisions.append(f"Scanning codebase files in `{owner}/{repo}` for latent bugs and security vulnerabilities.")
        repo_files = client.list_repository_files(owner=owner, repo=repo)
        scan_idx = 1
        for fpath in repo_files:
            try:
                f_res = client.get_repository_file(owner=owner, repo=repo, path=fpath)
                raw_text = f_res.get("raw_text") or ""
                if not raw_text and "content" in f_res:
                    raw_text = base64.b64decode(f_res["content"]).decode("utf-8", errors="ignore")
                defect = scan_code_for_defects(fpath, raw_text)
                if defect:
                    # Avoid duplicate if file is already tracked
                    if not any(a.get("file_path") == fpath for a in actionable):
                        is_act = defect["severity"] in ("CRITICAL", "HIGH")
                        defect_item = {
                            "id": 2000 + scan_idx,
                            "number": 100 + scan_idx,
                            "title": f"[{defect['cwe']}] {defect['title']}",
                            "body": defect["reason"],
                            "html_url": f"https://github.com/{owner}/{repo}/blob/main/{fpath}",
                            "author": "devpilot-scanner",
                            "labels": ["bug", defect["severity"].lower(), defect["cwe"].lower()],
                            "file_path": fpath,
                            "severity": defect["severity"],
                            "is_actionable": is_act,
                            "reason": defect["reason"],
                            "jira_ticket_key": None,
                            "pull_request_number": None,
                        }
                        analyzed.append(defect_item)
                        if is_act:
                            actionable.append(defect_item)
                            actions.append(f"Code scanner detected defect {defect['cwe']} in `{fpath}`.")
                        scan_idx += 1
            except Exception as e:
                logger.warning(f"Could not scan file {fpath}: {e}")

    decisions.append(
        f"Repository inspection complete: {len(analyzed)} item(s) inspected, "
        f"{len(actionable)} actionable bug(s) identified in `{owner}/{repo}`."
    )
    actions.append(f"Analyzed {len(analyzed)} items: identified {len(actionable)} actionable tasks.")

    return {
        "analyzed_issues": analyzed,
        "actionable_issues": actionable,
        "decisions": decisions,
        "actions_taken": actions,
    }


def inspect_code_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode github.content.get to read target source files."""
    actionable = state.get("actionable_issues", [])
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    inspected_files = []

    for issue in actionable:
        file_path = issue.get("file_path", "src/services/payment_service.py")
        decisions.append(f"Inspecting codebase: reading `{file_path}` for issue #{issue['number']}.")
        try:
            file_res = client.get_repository_file(owner=owner, repo=repo, path=file_path)
            raw_content = file_res.get("raw_text")
            if not raw_content and "content" in file_res:
                raw_content = base64.b64decode(file_res["content"]).decode("utf-8", errors="ignore")
            inspected_files.append({
                "path": file_path,
                "github_issue_number": issue["number"],
                "content": raw_content or "",
            })
            actions.append(f"Read codebase file `{file_path}` via Swytchcode github.content.get.")
        except Exception as e:
            err_msg = f"Failed to inspect code file `{file_path}`: {str(e)}"
            logger.error(err_msg)
            errors.append(err_msg)

    return {
        "inspected_files": inspected_files,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def generate_code_fix_node(state: DevPilotState) -> dict[str, Any]:
    """Diagnose code defects and generate patches with unified diffs."""
    actionable = state.get("actionable_issues", [])
    inspected_files = state.get("inspected_files", [])
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    file_map = {f["github_issue_number"]: f["content"] for f in inspected_files}
    patches = []

    for issue in actionable:
        issue_num = issue["number"]
        orig_code = file_map.get(issue_num, "")
        patch_info = diagnose_and_generate_patch(issue, orig_code)
        patches.append(patch_info)
        decisions.append(
            f"Code solution generated for #{issue_num} ({patch_info['file_path']}): {patch_info['explanation']}"
        )
        actions.append(f"Generated unified diff patch for `{patch_info['file_path']}`.")

    return {
        "code_patches": patches,
        "decisions": decisions,
        "actions_taken": actions,
    }


def create_pull_request_node(state: DevPilotState) -> dict[str, Any]:
    """Commit code patch and open GitHub Pull Request via Swytchcode."""
    patches = state.get("code_patches", [])
    actionable = state.get("actionable_issues", [])
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    pull_requests = []

    for patch in patches:
        issue_num = patch["github_issue_number"]
        file_path = patch["file_path"]
        fixed_content = patch["fixed_code"]
        branch_name = f"fix/gh-{issue_num}-{os.path.basename(file_path).split('.')[0]}"
        commit_msg = f"fix: resolve GitHub issue #{issue_num} in {file_path}"
        pr_title = f"[DevPilot Fix] Resolve #{issue_num} in {file_path}"
        pr_body = (
            f"### Automated Pull Request by DevPilot AI Software Engineer\n\n"
            f"**Target Issue:** #{issue_num}\n"
            f"**File Modified:** `{file_path}`\n\n"
            f"#### Summary of Changes\n"
            f"{patch['explanation']}\n\n"
            f"#### Diff\n"
            f"```diff\n{patch['diff']}\n```"
        )

        try:
            # 1. Commit file change
            client.update_repository_file(
                owner=owner,
                repo=repo,
                path=file_path,
                content=fixed_content,
                message=commit_msg,
                branch=branch_name,
            )
            # 2. Create PR
            pr_res = client.create_pull_request(
                owner=owner,
                repo=repo,
                title=pr_title,
                head=branch_name,
                base="main",
                body=pr_body,
            )
            pr_num = pr_res.get("number", 45)
            pull_requests.append(pr_res)

            # Link PR number to corresponding actionable issue
            for issue in actionable:
                if issue["number"] == issue_num:
                    issue["pull_request_number"] = pr_num

            decisions.append(f"Pull request #{pr_num} opened on branch `{branch_name}`.")
            actions.append(f"Created GitHub Pull Request #{pr_num}: '{pr_title}'.")
        except Exception as e:
            err_msg = f"Failed to create PR for #{issue_num}: {str(e)}"
            logger.error(err_msg)
            errors.append(err_msg)

    return {
        "actionable_issues": actionable,
        "pull_requests": pull_requests,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def create_jira_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode jira.api.issue.create linking GitHub issue and PR."""
    actionable = state.get("actionable_issues", [])
    project_key = state.get("jira_project") or os.getenv("JIRA_PROJECT_KEY", "DEV")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    jira_results = []

    decisions.append(f"Jira selected: creating tasks in project `{project_key}` for {len(actionable)} actionable item(s).")

    for issue in actionable:
        issue_num = issue["number"]
        pr_num = issue.get("pull_request_number")
        pr_note = f"Pull Request: #{pr_num}\n" if pr_num else ""
        summary = f"[GH-{issue_num}] {issue['title']}"
        desc = (
            f"Automated task created by DevPilot Agent for GitHub Issue #{issue_num}.\n\n"
            f"Severity: {issue['severity']}\n"
            f"Triage Assessment: {issue['reason']}\n"
            f"GitHub Link: {issue['html_url']}\n"
            f"{pr_note}\n"
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
                pull_request_number=pr_num,
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
    pull_requests = state.get("pull_requests", [])
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])
    errors = state.get("errors", [])
    slack_results = []

    decisions.append(f"Slack selected: notifying channel `{channel}` of engineering updates.")
    message_text = format_slack_message(jira_results, actionable, pull_requests, repo_name)

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
    """Synthesize complete final summary, code patches, traceability, and audit trail."""
    user_request = state.get("user_request", "")
    task_type = state.get("task_type", "issue_triage")
    analyzed = state.get("analyzed_issues", [])
    actionable = state.get("actionable_issues", [])
    patches = state.get("code_patches", [])
    pull_requests = state.get("pull_requests", [])
    jira_results = state.get("jira_results", [])
    slack_results = state.get("slack_results", [])
    errors = state.get("errors", [])
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    lines = []
    lines.append(f"### DevPilot AI Software Engineer Report")
    lines.append(f"**Task Type:** `{task_type}` | **User Request:** \"{user_request}\"\n")

    # High-level outcome
    lines.append("#### Executive Summary")
    lines.append(f"- **Issues Triaged:** {len(analyzed)}")
    lines.append(f"- **Actionable Issues Found:** {len(actionable)}")
    lines.append(f"- **Code Patches Generated:** {len(patches)}")
    lines.append(f"- **Pull Requests Opened:** {len(pull_requests)}")
    lines.append(f"- **Jira Tasks Created:** {len(jira_results)}")
    lines.append(f"- **Slack Notifications Dispatched:** {len(slack_results)}")

    if errors:
        lines.append("\n#### ⚠️ Errors / Warnings Encountered")
        for err in errors:
            lines.append(f"- {err}")

    # Code Diffs
    if patches:
        lines.append("\n#### 💻 Code Patches & Pull Requests")
        for patch in patches:
            pr_info = ""
            for pr in pull_requests:
                if f"#{patch['github_issue_number']}" in pr.get("title", ""):
                    pr_info = f" | **PR:** [{pr.get('title')}]({pr.get('html_url')})"
            lines.append(f"**File:** `{patch['file_path']}` (Issue #{patch['github_issue_number']}){pr_info}")
            lines.append(f"*{patch['explanation']}*\n")
            lines.append(f"```diff\n{patch['diff']}\n```\n")

    # Traceability Matrix
    if actionable:
        lines.append("#### 🔗 Complete Software Engineering Traceability")
        lines.append("| GitHub Issue | Severity | Code Patch | Pull Request | Jira Task | Slack Alert |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for item in actionable:
            gh_link = f"#{item['number']}"
            sev = item["severity"]
            has_patch = "✅ Generated" if any(p["github_issue_number"] == item["number"] for p in patches) else "—"
            pr_num = item.get("pull_request_number")
            pr_display = f"`PR #{pr_num}`" if pr_num else "—"
            jira_key = item.get("jira_ticket_key") or "—"
            slack_status = "Dispatched" if slack_results else "—"
            lines.append(f"| {gh_link} | **{sev}** | {has_patch} | {pr_display} | `{jira_key}` | {slack_status} |")

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
    """Conditionally route after issue triage based on user intent."""
    intent = state.get("intent", {})
    actionable = state.get("actionable_issues", [])

    if intent.get("needs_code_fix", False) and actionable:
        return "inspect_code"

    should_jira, _ = should_create_jira(intent, actionable)
    if should_jira:
        return "create_jira"

    should_slack, _ = should_send_slack(intent, [], actionable, [])
    if should_slack:
        return "send_slack"

    return "synthesize_response"


def route_after_code_fix(state: DevPilotState) -> str:
    """Route after generating code patches."""
    intent = state.get("intent", {})
    patches = state.get("code_patches", [])

    if intent.get("needs_pr", False) and patches:
        return "create_pull_request"

    actionable = state.get("actionable_issues", [])
    should_jira, _ = should_create_jira(intent, actionable)
    if should_jira:
        return "create_jira"

    should_slack, _ = should_send_slack(intent, [], actionable, [])
    if should_slack:
        return "send_slack"

    return "synthesize_response"


def route_after_pull_request(state: DevPilotState) -> str:
    """Route after opening Pull Requests."""
    intent = state.get("intent", {})
    actionable = state.get("actionable_issues", [])
    pull_requests = state.get("pull_requests", [])

    should_jira, _ = should_create_jira(intent, actionable)
    if should_jira:
        return "create_jira"

    should_slack, _ = should_send_slack(intent, [], actionable, pull_requests)
    if should_slack:
        return "send_slack"

    return "synthesize_response"


def route_after_jira(state: DevPilotState) -> str:
    """Conditionally route after Jira task creation to Slack or final response."""
    intent = state.get("intent", {})
    jira_results = state.get("jira_results", [])
    actionable = state.get("actionable_issues", [])
    pull_requests = state.get("pull_requests", [])

    should_slack, _ = should_send_slack(intent, jira_results, actionable, pull_requests)
    if should_slack:
        return "send_slack"

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
    workflow.add_node("inspect_code", inspect_code_node)
    workflow.add_node("generate_code_fix", generate_code_fix_node)
    workflow.add_node("create_pull_request", create_pull_request_node)
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
            "inspect_code": "inspect_code",
            "create_jira": "create_jira",
            "send_slack": "send_slack",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_edge("inspect_code", "generate_code_fix")

    workflow.add_conditional_edges(
        "generate_code_fix",
        route_after_code_fix,
        {
            "create_pull_request": "create_pull_request",
            "create_jira": "create_jira",
            "send_slack": "send_slack",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_conditional_edges(
        "create_pull_request",
        route_after_pull_request,
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
    """Execute the complete DevPilot LangGraph workflow."""
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
        "inspected_files": [],
        "code_patches": [],
        "pull_requests": [],
        "jira_results": [],
        "slack_results": [],
        "actions_taken": [],
        "decisions": [],
        "errors": [],
        "final_response": "",
    }

    final_state = app.invoke(initial_state)
    return final_state
