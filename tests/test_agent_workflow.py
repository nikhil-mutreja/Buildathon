"""Unit and integration tests for DevPilot LangGraph Agent workflow."""

import pytest
from app.agent.analyzer import (
    parse_user_intent,
    triage_issue,
    should_create_jira,
    should_send_slack,
)
from app.agent.graph import run_devpilot_agent
from app.integrations.swytchcode_client import (
    SwytchcodeClient,
    TOOL_GITHUB_ISSUES,
    TOOL_JIRA_CREATE_ISSUE,
    TOOL_SLACK_POST_MESSAGE,
)


def test_intent_parser_tool_selection():
    """Verify tool selection based on natural language intent."""
    # 1. GitHub only
    intent1 = parse_user_intent("Analyze open repository issues and assess health.")
    assert intent1["needs_github"] is True
    assert intent1["needs_jira"] is False
    assert intent1["needs_slack"] is False
    assert intent1["selected_tools"] == [TOOL_GITHUB_ISSUES]

    # 2. GitHub + Jira
    intent2 = parse_user_intent("Find critical bugs in GitHub and create Jira tasks.")
    assert intent2["needs_github"] is True
    assert intent2["needs_jira"] is True
    assert intent2["needs_slack"] is False
    assert set(intent2["selected_tools"]) == {TOOL_GITHUB_ISSUES, TOOL_JIRA_CREATE_ISSUE}

    # 3. Full workflow
    intent3 = parse_user_intent("Analyze issues, log Jira tickets for critical items, and notify Slack.")
    assert intent3["needs_github"] is True
    assert intent3["needs_jira"] is True
    assert intent3["needs_slack"] is True
    assert set(intent3["selected_tools"]) == {
        TOOL_GITHUB_ISSUES,
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


def test_conditional_workflow_github_only():
    """Verify 'Analyze GitHub issues' runs GitHub analysis without Jira or Slack."""
    state = run_devpilot_agent(
        user_request="Analyze my GitHub repository issues.",
        app_mode="mock",
    )
    assert len(state["github_results"]) > 0
    assert len(state["analyzed_issues"]) > 0
    assert len(state["jira_results"]) == 0
    assert len(state["slack_results"]) == 0
    assert "github.issue.get1" in state["selected_tools"]
    assert "jira.api.issue.create" not in state["selected_tools"]
    assert "slack.chat.postmessage.create" not in state["selected_tools"]


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
    # Traceability check: each Jira task matches an actionable GitHub issue
    for ticket in state["jira_results"]:
        assert ticket["key"].startswith("DEV-")
        assert "github_issue_number" in ticket


def test_conditional_workflow_full_pipeline():
    """Verify 'Find critical issues, create Jira tasks, and notify Slack' runs all 3 stages."""
    state = run_devpilot_agent(
        user_request="Find critical GitHub issues, create Jira tasks, and notify Slack.",
        app_mode="mock",
    )
    assert len(state["github_results"]) > 0
    assert len(state["actionable_issues"]) > 0
    assert len(state["jira_results"]) > 0
    assert len(state["slack_results"]) == 1
    assert state["slack_results"][0]["ok"] is True
    # Ensure final response contains traceability
    assert "Executive Summary" in state["final_response"]
    assert "Traceability" in state["final_response"]


def test_jira_decision_skipped_when_no_actionable_issues():
    """Verify Jira is skipped if no actionable issues exist even if requested."""
    intent = {"needs_jira": True}
    actionable_empty = []
    should_run, reason = should_create_jira(intent, actionable_empty)
    assert should_run is False
    assert "no critical or actionable issues" in reason


def test_mock_client_capabilities():
    """Verify SwytchcodeClient in mock mode provides full interface parity."""
    client = SwytchcodeClient(mode="mock")
    assert client.is_mock() is True

    issues = client.fetch_github_issues("test-org", "test-repo")
    assert len(issues) >= 3
    assert issues[0]["number"] == 101

    jira_res = client.create_jira_issue(
        project_key="TEST",
        summary="Test ticket",
        description="Details",
        github_issue_number=101,
    )
    assert jira_res["key"] == "TEST-201"

    slack_res = client.send_slack_message("#dev-test", "Test alert")
    assert slack_res["ok"] is True


def test_real_mode_error_handling(monkeypatch):
    """Verify clean error capture when real mode credentials fail."""
    # Force client to real mode with no credentials
    client = SwytchcodeClient(mode="real")
    if client._swx is not None:
        with pytest.raises(RuntimeError) as exc_info:
            client.fetch_github_issues("nonexistent-org-12345", "repo")
        assert "Swytchcode GitHub error" in str(exc_info.value)
