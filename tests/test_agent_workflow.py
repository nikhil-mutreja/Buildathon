"""Unit and integration tests for DevPilot AI Software Engineer LangGraph Agent."""

import pytest
from app.agent.analyzer import (
    parse_user_intent,
    triage_issue,
    diagnose_and_generate_patch,
    should_create_jira,
    should_send_slack,
)
from app.agent.graph import run_devpilot_agent
from app.integrations.swytchcode_client import (
    SwytchcodeClient,
    TOOL_GITHUB_ISSUES,
    TOOL_GITHUB_CONTENT_GET,
    TOOL_GITHUB_CONTENT_UPDATE,
    TOOL_GITHUB_PULL_CREATE,
    TOOL_JIRA_CREATE_ISSUE,
    TOOL_SLACK_POST_MESSAGE,
)


def test_intent_parser_tool_selection():
    """Verify tool selection based on natural language intent."""
    # 1. GitHub only
    intent1 = parse_user_intent("Analyze open repository issues and assess health.")
    assert intent1["needs_github"] is True
    assert intent1["needs_code_fix"] is False
    assert intent1["needs_jira"] is False
    assert intent1["needs_slack"] is False
    assert intent1["selected_tools"] == [TOOL_GITHUB_ISSUES]

    # 2. GitHub + Jira
    intent2 = parse_user_intent("Find critical bugs in GitHub and create Jira tasks.")
    assert intent2["needs_github"] is True
    assert intent2["needs_code_fix"] is False
    assert intent2["needs_jira"] is True
    assert intent2["needs_slack"] is False
    assert set(intent2["selected_tools"]) == {TOOL_GITHUB_ISSUES, TOOL_JIRA_CREATE_ISSUE}

    # 3. Autonomous Coding Task (Fix Bug + PR + Jira + Slack)
    intent3 = parse_user_intent(
        "Fix bug #102: payment gateway 500 error, open pull request, create Jira task, and notify Slack."
    )
    assert intent3["task_type"] == "bug_fix"
    assert intent3["target_issue_number"] == 102
    assert intent3["needs_code_fix"] is True
    assert intent3["needs_pr"] is True
    assert intent3["needs_jira"] is True
    assert intent3["needs_slack"] is True
    assert set(intent3["selected_tools"]) == {
        TOOL_GITHUB_ISSUES,
        TOOL_GITHUB_CONTENT_GET,
        TOOL_GITHUB_CONTENT_UPDATE,
        TOOL_GITHUB_PULL_CREATE,
        TOOL_JIRA_CREATE_ISSUE,
        TOOL_SLACK_POST_MESSAGE,
    }


def test_issue_triage_classification():
    """Verify triage logic categorizes severity and actionability accurately."""
    # Security vulnerability -> CRITICAL & actionable
    sec_issue = {
        "id": 1,
        "number": 101,
        "title": "OAuth callback token leak vulnerability",
        "body": "User tokens leaked in headers",
        "labels": [{"name": "security"}],
    }
    res_sec = triage_issue(sec_issue)
    assert res_sec["severity"] == "CRITICAL"
    assert res_sec["is_actionable"] is True
    assert "security" in res_sec["reason"].lower()

    # 500 error / outage -> CRITICAL & actionable
    outage_issue = {
        "id": 2,
        "number": 102,
        "title": "Payment gateway returns HTTP 500 on checkout",
        "body": "Production incident",
        "labels": [{"name": "p0"}],
    }
    res_outage = triage_issue(outage_issue)
    assert res_outage["severity"] == "CRITICAL"
    assert res_outage["is_actionable"] is True

    # Memory leak -> HIGH & actionable
    perf_issue = {
        "id": 3,
        "number": 103,
        "title": "Memory leak in WebSocket broker",
        "body": "Leaks memory over time",
        "labels": [{"name": "performance"}],
    }
    res_perf = triage_issue(perf_issue)
    assert res_perf["severity"] == "HIGH"
    assert res_perf["is_actionable"] is True

    # Docs typo -> LOW & not actionable
    doc_issue = {
        "id": 4,
        "number": 104,
        "title": "Fix typo in README documentation",
        "body": "Small spelling correction",
        "labels": [{"name": "documentation"}],
    }
    res_doc = triage_issue(doc_issue)
    assert res_doc["severity"] == "LOW"
    assert res_doc["is_actionable"] is False


def test_code_patch_generation():
    """Verify that diagnose_and_generate_patch produces a valid unified diff."""
    issue = {
        "number": 102,
        "title": "Payment gateway returns HTTP 500",
        "file_path": "src/services/payment_service.py",
    }
    orig_code = (
        "def process_transaction(amount, currency, exchange_rate):\n"
        "    converted = float(amount) / exchange_rate\n"
        "    return converted\n"
    )
    patch = diagnose_and_generate_patch(issue, orig_code)
    assert patch["file_path"] == "src/services/payment_service.py"
    assert "Decimal" in patch["fixed_code"]
    assert "--- a/src/services/payment_service.py" in patch["diff"]
    assert "+++ b/src/services/payment_service.py" in patch["diff"]


def test_autonomous_coding_workflow_bug_fix():
    """Verify complete end-to-end software engineering workflow with code fix and PR."""
    state = run_devpilot_agent(
        user_request="Investigate and fix bug #102: payment gateway 500 error, open a pull request, create a Jira task, and notify Slack.",
        app_mode="mock",
    )
    # 1. Actionable issue identified
    assert len(state["actionable_issues"]) == 1
    assert state["actionable_issues"][0]["number"] == 102

    # 2. File inspected
    assert len(state["inspected_files"]) == 1
    assert "payment_service" in state["inspected_files"][0]["path"]

    # 3. Patch generated
    assert len(state["code_patches"]) == 1
    assert "Decimal" in state["code_patches"][0]["fixed_code"]

    # 4. Pull request created
    assert len(state["pull_requests"]) == 1
    pr = state["pull_requests"][0]
    assert pr["number"] > 0
    assert "pull" in pr["html_url"]

    # 5. Jira task created with linked PR
    assert len(state["jira_results"]) == 1
    jira_res = state["jira_results"][0]
    assert jira_res["key"].startswith("DEV-")

    # 6. Slack notification sent
    assert len(state["slack_results"]) == 1
    assert state["slack_results"][0]["ok"] is True

    # 7. Traceability in final response
    assert "Code Patches & Pull Requests" in state["final_response"]
    assert f"#{pr['number']}" in state["final_response"]


def test_conditional_workflow_github_only():
    """Verify 'Analyze GitHub issues' runs GitHub analysis without Jira or Slack."""
    state = run_devpilot_agent(
        user_request="Analyze my GitHub repository issues.",
        app_mode="mock",
    )
    assert len(state["github_results"]) > 0
    assert len(state["analyzed_issues"]) > 0
    assert len(state["code_patches"]) == 0
    assert len(state["pull_requests"]) == 0
    assert len(state["jira_results"]) == 0
    assert len(state["slack_results"]) == 0


def test_conditional_workflow_github_and_jira():
    """Verify 'Analyze critical issues and create Jira tasks' runs GitHub + Jira only."""
    state = run_devpilot_agent(
        user_request="Analyze critical GitHub issues and create Jira tasks.",
        app_mode="mock",
    )
    assert len(state["github_results"]) > 0
    assert len(state["actionable_issues"]) > 0
    assert len(state["jira_results"]) > 0
    assert len(state["slack_results"]) == 0


def test_mock_client_capabilities():
    """Verify SwytchcodeClient in mock mode provides full interface parity."""
    client = SwytchcodeClient(mode="mock")
    assert client.is_mock() is True

    # Issues
    issues = client.fetch_github_issues("test-org", "test-repo")
    assert len(issues) >= 3

    # File get
    f = client.get_repository_file("test-org", "test-repo", "src/services/payment_service.py")
    assert "payment_service" in f["path"]

    # File update
    up = client.update_repository_file("test-org", "test-repo", "src/services/payment_service.py", "new_code", "msg", "fix-branch")
    assert "commit" in up

    # PR create
    pr = client.create_pull_request("test-org", "test-repo", "Fix title", "fix-branch")
    assert pr["number"] > 0

    # Jira
    jira_res = client.create_jira_issue(
        project_key="TEST",
        summary="Test ticket",
        description="Details",
        github_issue_number=101,
        pull_request_number=pr["number"],
    )
    assert jira_res["key"] == "TEST-201"

    # Slack
    slack_res = client.send_slack_message("#dev-test", "Test alert")
    assert slack_res["ok"] is True


def test_option_security_token_leak_workflow():
    """Option 2: Check repo, find OAuth token leak (#101), fix code, open PR, Jira, Slack."""
    state = run_devpilot_agent(
        user_request="Check the repo, find the OAuth token leak security vulnerability #101, fix the code in oauth_handler.py, open a pull request, create a Jira task, and notify Slack.",
        app_mode="mock",
    )
    assert len(state["actionable_issues"]) == 1
    assert state["actionable_issues"][0]["number"] == 101
    assert "oauth_handler.py" in state["inspected_files"][0]["path"]
    assert "masked_token" in state["code_patches"][0]["fixed_code"]
    assert len(state["pull_requests"]) == 1
    assert "Resolve #101" in state["pull_requests"][0]["title"]
    assert len(state["jira_results"]) == 1
    assert state["jira_results"][0]["key"] == "DEV-201"
    assert len(state["slack_results"]) == 1


def test_option_websocket_memory_leak_workflow():
    """Option 3: Check repo, find WebSocket memory leak (#103), fix code, open PR, Jira, Slack."""
    state = run_devpilot_agent(
        user_request="Check the repo, find the WebSocket connection pool memory leak #103, fix the code in broker.py, open a pull request, create a Jira task, and notify Slack.",
        app_mode="mock",
    )
    assert len(state["actionable_issues"]) == 1
    assert state["actionable_issues"][0]["number"] == 103
    assert "broker.py" in state["inspected_files"][0]["path"]
    assert "WeakSet" in state["code_patches"][0]["fixed_code"]
    assert len(state["pull_requests"]) == 1
    assert "Resolve #103" in state["pull_requests"][0]["title"]
    assert len(state["jira_results"]) == 1
    assert state["jira_results"][0]["key"] == "DEV-203"
    assert len(state["slack_results"]) == 1


def test_option_multi_bug_autonomous_sweep():
    """Option 4: Autonomous multi-bug sweep across repo, fixing all critical defects, opening PRs."""
    state = run_devpilot_agent(
        user_request="Check the repo, find all critical bugs, fix each of them in the codebase, open pull requests, create Jira tasks, and notify Slack.",
        app_mode="mock",
    )
    assert len(state["actionable_issues"]) == 3
    assert len(state["inspected_files"]) == 3
    assert len(state["code_patches"]) == 3
    assert len(state["pull_requests"]) == 3
    assert len(state["jira_results"]) == 3
    assert len(state["slack_results"]) == 1
    # Check that all 3 PRs exist
    pr_titles = [pr["title"] for pr in state["pull_requests"]]
    assert any("#101" in t for t in pr_titles)
    assert any("#102" in t for t in pr_titles)
    assert any("#103" in t for t in pr_titles)


def test_user_natural_language_request_check_fix_open_pr():
    """Verify exact user instruction: check repo, find bug, fix it, open PR."""
    state = run_devpilot_agent(
        user_request="this agent go and check the repo after that found bug in them after founding bug it must fix it and open pr",
        app_mode="mock",
    )
    assert state["task_type"] == "bug_fix"
    assert len(state["inspected_files"]) >= 1
    assert len(state["code_patches"]) >= 1
    assert len(state["pull_requests"]) >= 1

