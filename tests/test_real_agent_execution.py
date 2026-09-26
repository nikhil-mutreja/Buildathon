"""Rigorous end-to-end verification tests for Real Mode and Safety Gate in DevPilot."""

import os
import subprocess
import pytest
from app.agent.graph import run_devpilot_agent
from app.integrations.swytchcode_client import SwytchcodeClient


def test_real_agent_full_lifecycle_on_controlled_repo():
    """Verify Section 28 & 29: End-to-end real agent workflow on real_test_repo."""
    workspace = "/home/nikhil-mutreja/buildathon"
    repo_path = os.path.join(workspace, "test_repositories/real_test_repo")

    # 1. Verify baseline test fails before agent runs
    env = {**os.environ, "PYTHONPATH": repo_path}
    pre_test = subprocess.run(
        ["/home/nikhil-mutreja/buildathon/.venv/bin/pytest", os.path.join(repo_path, "tests"), "-v"],
        cwd=repo_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert pre_test.returncode != 0, "Baseline test should fail before fix is applied"
    assert "2 failed, 1 passed" in pre_test.stdout or "FAILED" in pre_test.stdout

    # 2. Run agent in REAL mode
    state = run_devpilot_agent(
        user_request=(
            "Access repository test_repositories/real_test_repo, read real issue #1, "
            "inspect src/greeter.py, understand why it fails for empty/whitespace names, "
            "modify the code to fix the defect, run the tests to verify the fix, "
            "create a real git branch, commit the changes, and open a pull request for senior review authored by @nikhil-mutreja"
        ),
        repo_owner="nikhil-mutreja",
        repo_name="test_repositories/real_test_repo",
        github_username="nikhil-mutreja",
        app_mode="real",
    )

    # 3. Verify real issue retrieved
    assert len(state["github_results"]) >= 1
    assert state["github_results"][0]["number"] == 1
    assert "greet" in state["github_results"][0]["title"].lower()

    # 4. Verify code patch and file modification
    assert len(state["code_patches"]) >= 1
    patch = state["code_patches"][0]
    assert patch["file_path"] == "src/greeter.py"
    assert "Anonymous" in patch["fixed_code"]

    # 5. Verify automated test execution (Section 8)
    test_res = state["test_results"]
    assert test_res["passed"] is True
    assert test_res["status"] == "TEST PASSED"
    assert test_res["exit_code"] == 0
    assert "3 passed" in test_res["summary"] or "passed" in test_res["summary"]
    assert state["can_proceed"] is True

    # 6. Verify real Git branch creation (Section 10)
    assert state["git_branch"] == "fix/nikhil-mutreja-gh-1-greeter"
    git_b = subprocess.run(["git", "branch", "--show-current"], cwd=repo_path, capture_output=True, text=True)
    assert git_b.stdout.strip() == "fix/nikhil-mutreja-gh-1-greeter"

    # 7. Verify real Git commit with actual 40-character SHA (Section 11)
    sha = state["commit_sha"]
    assert len(sha) == 40
    assert "mock" not in sha
    git_log = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True)
    assert git_log.stdout.strip() == sha

    # 8. Verify honest PR reporting without fake PR numbers (Section 12)
    # Inside the sandbox, live Swytchcode/GitHub remote call reports the actual environment status
    assert len(state["pull_requests"]) == 0
    assert state["pr_error"] is not None
    assert "mock" not in state["pr_error"].lower()

    # 9. Verify transparent final response audit trail (Section 16)
    resp = state["final_response"]
    assert "REAL MODE" in resp
    assert "fix/nikhil-mutreja-gh-1-greeter" in resp
    assert sha in resp
    assert "TEST PASSED" in resp


def test_safety_gate_blocks_branching_and_pr_on_failing_tests():
    """Verify Section 9: If automated tests fail, agent halts and never creates branch, commit, or PR."""
    workspace = "/home/nikhil-mutreja/buildathon"
    repo_path = os.path.join(workspace, "test_repositories/real_test_repo")

    # Initialize client and simulate test runner failure
    client = SwytchcodeClient(mode="real")
    
    # Intentionally corrupt greeter.py with broken code that fails tests
    broken_code = "def greet(name: str) -> str:\n    return 'Broken Greeting'\n"
    client.update_repository_file("nikhil-mutreja", repo_path, "src/greeter.py", broken_code, "test: broken", "main")

    # Run tests directly to verify failure
    t_res = client.run_tests("nikhil-mutreja", repo_path)
    assert t_res["passed"] is False
    assert t_res["status"] == "TEST FAILED"

    # Verify that in DevPilot workflow, when tests fail, safety gate halts before git operations
    from app.agent.graph import build_devpilot_graph
    graph = build_devpilot_graph()

    failing_state = {
        "user_request": "Fix greeter issue #1",
        "repo_owner": "nikhil-mutreja",
        "repo_name": repo_path,
        "github_username": "nikhil-mutreja",
        "app_mode": "real",
        "intent": {"needs_github": True, "needs_code_fix": True, "needs_pr": True},
        "actionable_issues": [{"number": 1, "file_path": "src/greeter.py", "title": "Test Issue", "severity": "HIGH"}],
        "code_patches": [{"github_issue_number": 1, "file_path": "src/greeter.py", "fixed_code": broken_code, "diff": "", "explanation": "Broken test patch"}],
        "can_proceed": False,
        "git_branch": "",
        "commit_sha": "",
        "pull_requests": [],
        "errors": [],
        "actions_taken": [],
        "decisions": [],
    }

    # Execute run_tests node
    from app.agent.graph import run_tests_node, route_after_run_tests
    test_node_res = run_tests_node(failing_state)
    assert test_node_res["can_proceed"] is False
    assert test_node_res["test_results"]["status"] == "TEST FAILED"

    # Verify safety gate routing blocks create_git_branch
    next_node = route_after_run_tests({**failing_state, **test_node_res})
    assert next_node == "synthesize_response", f"Expected synthesize_response, got {next_node}"
    assert next_node != "create_git_branch"


def test_investigate_only_workflow():
    """Verify Section 15: Investigate-only mode does not modify code or open PR."""
    state = run_devpilot_agent(
        user_request="Investigate only: check issue #1 in test_repositories/real_test_repo. Do not modify files or create a PR.",
        repo_owner="nikhil-mutreja",
        repo_name="test_repositories/real_test_repo",
        app_mode="real",
    )
    assert state["intent"]["investigate_only"] is True
    assert state["intent"]["needs_code_fix"] is False
    assert state["intent"]["needs_pr"] is False
    assert len(state["code_patches"]) == 0
    assert len(state["pull_requests"]) == 0
    assert state["git_branch"] == ""
    assert state["commit_sha"] == ""
