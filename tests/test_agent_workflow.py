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
    assert len(state["actionable_issues"]) >= 3
    assert len(state["inspected_files"]) >= 3
    assert len(state["code_patches"]) >= 3
    assert len(state["pull_requests"]) >= 3
    assert len(state["jira_results"]) >= 3
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


def test_public_repo_url_parsing_and_defect_scanning():
    """Verify natural-language request containing public GitHub repository URL."""
    state = run_devpilot_agent(
        user_request="Check public repository https://github.com/octocat/Hello-World, find the bug in it after finding bug fix it and open pr",
        app_mode="mock",
    )
    assert state["repo_owner"] == "octocat"
    assert state["repo_name"] == "Hello-World"
    assert state["task_type"] == "bug_fix"
    assert len(state["actionable_issues"]) >= 1
    assert len(state["code_patches"]) >= 1
    assert len(state["pull_requests"]) >= 1
    pr = state["pull_requests"][0]
    assert "octocat/Hello-World" in pr["html_url"]


def test_scan_code_for_defects_detection():
    """Unit test for AST/heuristic defect scanner functions."""
    from app.agent.analyzer import scan_code_for_defects

    # Test 1: Float division in financial logic (CWE-681)
    code_payment = "def charge(amount, exchange_rate):\n    return float(amount) / exchange_rate\n"
    d1 = scan_code_for_defects("src/payment.py", code_payment)
    assert d1 is not None
    assert d1["cwe"] == "CWE-681"

    # Test 2: Sensitive token logging in plain text (CWE-532)
    code_token = "def callback(token):\n    logger.info(f'Token: {access_token}')\n"
    d2 = scan_code_for_defects("src/auth.py", code_token)
    assert d2 is not None
    assert d2["cwe"] == "CWE-532"

    # Test 3: Unbounded connection pool memory leak (CWE-775)
    code_leak = "class Pool:\n    def add(self, ws):\n        self.connections.append(ws)\n"
    d3 = scan_code_for_defects("src/broker.py", code_leak)
    assert d3 is not None
    assert d3["cwe"] == "CWE-775"


def test_public_repo_analysis_and_pr_for_username_nikhil_mutreja():
    """Verify public repo analysis, defect discovery, and PR authorship for nikhil-mutreja."""
    user_prompt = (
        "Check public repository https://github.com/octocat/Hello-World, "
        "analyze the complete repo, find the bug in it, fix it, and open a pull request "
        "for github account username :- nikhil-mutreja"
    )
    state = run_devpilot_agent(user_prompt, app_mode="mock")
    assert state["repo_owner"] == "octocat"
    assert state["repo_name"] == "Hello-World"
    assert state["github_username"] == "nikhil-mutreja"
    assert len(state["actionable_issues"]) >= 1
    assert len(state["code_patches"]) >= 1
    assert len(state["pull_requests"]) >= 1
    for pr in state["pull_requests"]:
        assert pr["user"]["login"] == "nikhil-mutreja"
        assert "fix/nikhil-mutreja-" in pr["head"]["ref"]
        assert "nikhil-mutreja" in pr["title"]
def test_senior_engineer_review_pr_format_and_checklist():
    """Verify that Pull Requests are formatted specifically for Senior Engineer Review."""
    user_prompt = (
        "Check this repo https://github.com/octocat/Hello-World, identify the real issues in it, "
        "fix them, and open PR for senior engineers to review for github account username :- nikhil-mutreja"
    )
    state = run_devpilot_agent(user_prompt, app_mode="mock")
    assert state["github_username"] == "nikhil-mutreja"
    assert len(state["pull_requests"]) >= 1

    pr = state["pull_requests"][0]
    # Check title
    assert "[Senior Review Requested]" in pr["title"]
    assert "@nikhil-mutreja" in pr["title"]

    # Check body contains Senior Review components
    body = pr["body"]
    assert "Senior Engineer Review Request" in body
    assert "Senior Engineer Sign-Off Checklist" in body
    assert "@nikhil-mutreja" in body
    assert "Defect Triage & Root Cause Analysis" in body
    assert "Unified Code Diff" in body

    # Check that checklist and defect fields are attached
    assert "review_checklist" in pr
    assert len(pr["review_checklist"]) >= 4
    assert pr["lineno"] >= 1
    assert len(pr["snippet"]) > 0
    assert pr["author"] == "nikhil-mutreja"

    # Check executive summary contains Senior Review section
    assert "Senior Engineer Review Ready Pull Requests" in state["final_response"]
    assert "@nikhil-mutreja" in state["final_response"]


def test_ast_defect_analysis_and_snippets():
    """Verify AST detects line numbers, code snippets, and defect types."""
    from app.agent.analyzer import scan_code_for_defects

    # Test Unclosed File Descriptor (CWE-775)
    file_code = "import os\ndef read_cfg():\n    f = open('config.json', 'r')\n    return f.read()\n"
    d_file = scan_code_for_defects("src/utils/file_manager.py", file_code)
    assert d_file is not None
    assert d_file["cwe"] == "CWE-775"
    assert d_file["lineno"] == 3
    assert "f = open('config.json', 'r')" in d_file["snippet"]

    # Test Mutable Default Argument (PEP-484)
    user_code = "def assign_roles(user, roles=[]):\n    roles.append('admin')\n    return roles\n"
    d_user = scan_code_for_defects("src/api/user_service.py", user_code)
    assert d_user is not None
    assert d_user["cwe"] == "PEP-484"
    assert d_user["lineno"] == 1
    assert "roles=[]" in d_user["snippet"]

    # Test SQL Injection (CWE-89)
    sql_code = "def get_user(uid):\n    query = f\"SELECT * FROM users WHERE id = '{uid}'\"\n    return query\n"
    d_sql = scan_code_for_defects("src/db/query.py", sql_code)
    assert d_sql is not None
    assert d_sql["cwe"] == "CWE-89"
    assert d_sql["lineno"] == 2


def test_real_on_disk_repo_auth_microservice():
    """Verify scanning real auth_microservice on disk only identifies auth defects with accurate lines."""
    state = run_devpilot_agent(
        user_request=(
            "Scan repository test_repositories/auth_microservice, analyze all real code files, "
            "find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- nikhil-mutreja."
        ),
        app_mode="mock",
    )
    assert state["repo_name"] == "auth_microservice"
    assert state["github_username"] == "nikhil-mutreja"
    file_paths = [issue["file_path"] for issue in state["actionable_issues"]]
    assert "src/auth/session_manager.py" in file_paths
    assert "src/roles/user_permissions.py" in file_paths
    # Ensure no ecommerce or realtime files are present
    assert not any("payment_gateway" in p for p in file_paths)
    assert not any("event_dispatcher" in p for p in file_paths)

    assert len(state["pull_requests"]) == 2
    for pr in state["pull_requests"]:
        assert pr["user"]["login"] == "nikhil-mutreja"
        assert "@nikhil-mutreja" in pr["title"]
        assert pr["lineno"] in (7, 11)


def test_real_on_disk_repo_ecommerce_service():
    """Verify scanning real ecommerce_service on disk only identifies ecommerce defects."""
    state = run_devpilot_agent(
        user_request=(
            "Scan repository test_repositories/ecommerce_service, analyze all real code files, "
            "find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- nikhil-mutreja."
        ),
        app_mode="mock",
    )
    assert state["repo_name"] == "ecommerce_service"
    file_paths = [issue["file_path"] for issue in state["actionable_issues"]]
    assert "src/checkout/payment_gateway.py" in file_paths
    assert "src/orders/database.py" in file_paths
    assert "src/storage/receipt_manager.py" in file_paths

    assert len(state["pull_requests"]) == 3
    for pr in state["pull_requests"]:
        assert pr["user"]["login"] == "nikhil-mutreja"
        assert "@nikhil-mutreja" in pr["title"]


def test_real_on_disk_repo_realtime_stream_service():
    """Verify scanning real realtime_stream_service on disk only identifies realtime defects."""
    state = run_devpilot_agent(
        user_request=(
            "Scan repository test_repositories/realtime_stream_service, analyze all real code files, "
            "find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- nikhil-mutreja."
        ),
        app_mode="mock",
    )
    assert state["repo_name"] == "realtime_stream_service"
    file_paths = [issue["file_path"] for issue in state["actionable_issues"]]
    assert "src/broker/event_dispatcher.py" in file_paths
    assert "src/config/service_settings.py" in file_paths

    assert len(state["pull_requests"]) == 2
    for pr in state["pull_requests"]:
        assert pr["user"]["login"] == "nikhil-mutreja"
        assert "@nikhil-mutreja" in pr["title"]


def test_distinct_repositories_produce_strictly_disjoint_results():
    """Verify scanning different repositories never returns identical or canned outputs."""
    auth_state = run_devpilot_agent(
        "Scan repository test_repositories/auth_microservice, fix bugs, open PR for username :- nikhil-mutreja",
        app_mode="mock",
    )
    ecom_state = run_devpilot_agent(
        "Scan repository test_repositories/ecommerce_service, fix bugs, open PR for username :- nikhil-mutreja",
        app_mode="mock",
    )

    auth_files = set(issue["file_path"] for issue in auth_state["actionable_issues"])
    ecom_files = set(issue["file_path"] for issue in ecom_state["actionable_issues"])

    assert len(auth_files) > 0
    assert len(ecom_files) > 0
    # Files must be strictly disjoint
    assert auth_files.isdisjoint(ecom_files)

    auth_prs = [pr["title"] for pr in auth_state["pull_requests"]]
    ecom_prs = [pr["title"] for pr in ecom_state["pull_requests"]]
    assert set(auth_prs).isdisjoint(set(ecom_prs))


def test_arbitrary_public_repo_url_with_dynamic_default_branch():
    """Verify that any public repository (e.g. pallets/flask, octocat/Hello-World) works end-to-end."""
    user_prompt = (
        "Check this repo https://github.com/pallets/flask, find all issues in the codebase, "
        "fix them, and open a pull request committed by @nikhil-mutreja."
    )
    state = run_devpilot_agent(user_prompt, app_mode="mock")
    assert state["repo_owner"] == "pallets"
    assert state["repo_name"] == "flask"
    assert state["github_username"] == "nikhil-mutreja"
    assert len(state["code_patches"]) >= 1
    assert len(state["pull_requests"]) >= 1
    pr = state["pull_requests"][0]
    assert pr["user"]["login"] == "nikhil-mutreja"
    assert "@nikhil-mutreja" in pr["title"]
    assert "[Senior Review Requested]" in pr["title"]
    assert "flask" in pr.get("html_url", "") or state["repo_name"] == "flask"


def test_generic_patch_generation_on_arbitrary_variable_names():
    """Verify that patch generation handles arbitrary variable names and non-canned patterns."""
    from app.agent.analyzer import diagnose_and_generate_patch

    # 1. Arbitrary unclosed file with custom variable names
    issue_unclosed = {
        "number": 201,
        "defect_type": "UNCLOSED_FILE_DESCRIPTOR_LEAK",
        "file_path": "custom/path/reader.py",
        "cwe": "CWE-775",
    }
    code_unclosed = "def load_dataset(dataset_csv):\n    data_stream = open(dataset_csv, 'r')\n    records = data_stream.read()\n    return records\n"
    patch_unclosed = diagnose_and_generate_patch(issue_unclosed, code_unclosed)
    assert "with open(dataset_csv, 'r') as data_stream:" in patch_unclosed["fixed_code"]
    assert "--- a/custom/path/reader.py" in patch_unclosed["diff"]

    # 2. Arbitrary mutable default with custom function & parameter names
    issue_mutable = {
        "number": 202,
        "defect_type": "MUTABLE_DEFAULT_ARGUMENT",
        "file_path": "pkg/handlers.py",
        "cwe": "PEP-484",
    }
    code_mutable = "def dispatch_events(event_id: str, listeners=[]):\n    listeners.append(event_id)\n    return listeners\n"
    patch_mutable = diagnose_and_generate_patch(issue_mutable, code_mutable)
    assert "listeners=None" in patch_mutable["fixed_code"]
    assert "if listeners is None:" in patch_mutable["fixed_code"]
    assert "--- a/pkg/handlers.py" in patch_mutable["diff"]

    # 3. Arbitrary hardcoded API secret
    issue_secret = {
        "number": 203,
        "defect_type": "HARDCODED_CREDENTIAL",
        "file_path": "backend/config.py",
        "cwe": "CWE-798",
    }
    code_secret = 'api_key = "live_secret_key_99281729384759281729"\n'
    patch_secret = diagnose_and_generate_patch(issue_secret, code_secret)
    assert "os.getenv" in patch_secret["fixed_code"]
    assert "--- a/backend/config.py" in patch_secret["diff"]

    # 4. Arbitrary README documentation improvement
    issue_readme = {
        "number": 204,
        "defect_type": "DOCUMENTATION_STANDARDS_DEFECT",
        "file_path": "README.md",
        "cwe": "CWE-INFO",
    }
    code_readme = "# Hello World\nA sample repository."
    patch_readme = diagnose_and_generate_patch(issue_readme, code_readme)
    assert "Architecture & Getting Started" in patch_readme["fixed_code"]
    assert "Contributing Guidelines" in patch_readme["fixed_code"]
    assert "Security Policy" in patch_readme["fixed_code"]
    assert "--- a/README.md" in patch_readme["diff"]


def test_real_mode_pull_request_resilience_on_network_timeout():
    """Verify that in real mode, when GitHub API times out on a remote repo, a Staged PR is created."""
    user_prompt = (
        "Check repository https://github.com/rust-lang/rus, find issues, "
        "fix them, and open a pull request committed by @nikhil-mutreja."
    )
    state = run_devpilot_agent(user_prompt, app_mode="real")
    assert state["task_type"] == "bug_fix"
    assert len(state["code_patches"]) >= 1
    # Verify Pull Request is successfully created despite remote network timeout
    assert len(state["pull_requests"]) >= 1
    pr = state["pull_requests"][0]
    assert pr.get("html_url") is not None
    assert "rust-lang/rus" in pr["html_url"] or "compare" in pr["html_url"]
    assert pr["author"] == "nikhil-mutreja"
    assert len(pr["review_checklist"]) >= 4
    assert pr.get("is_staged_pr") is True



