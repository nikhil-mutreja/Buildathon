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
    scan_all_defects_in_code,
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
    github_user = intent.get("target_github_username") or state.get("github_username") or os.getenv("GITHUB_USERNAME", "nikhil-mutreja")

    decisions = list(state.get("decisions", []))
    if intent.get("target_repo_owner") and intent.get("target_repo_name"):
        decisions.append(f"Target repository identified from request: `{repo_owner}/{repo_name}`.")
    decisions.append(f"Pull Request contributor identity configured as `@{github_user}`.")

    decisions.append(
        f"Task categorized as `{task_type}`. Intent: GitHub={intent['needs_github']}, "
        f"CodeFix={intent['needs_code_fix']}, PR={intent['needs_pr']}, "
        f"Jira={intent['needs_jira']}, Slack={intent['needs_slack']}."
    )

    actions = list(state.get("actions_taken", []))
    actions.append(f"Request understood: '{task_type}' task initialized for `{repo_owner}/{repo_name}` by @{github_user} with {len(selected_tools)} Swytchcode tools.")

    return {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "github_username": github_user,
        "task_type": task_type,
        "intent": intent,
        "selected_tools": selected_tools,
        "plan": plan,
        "decisions": decisions,
        "actions_taken": actions,
    }


def fetch_github_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode github.issue.get1 or inspect real repository issues."""
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    decisions.append(f"Accessing repository: retrieving issues for `{owner}/{repo}`.")

    try:
        issues = client.fetch_github_issues(owner=owner, repo=repo)
        actions.append(f"GitHub issues retrieved: {len(issues)} issue(s) fetched via Swytchcode/local repository.")
        return {
            "github_results": issues,
            "decisions": decisions,
            "actions_taken": actions,
            "errors": errors,
        }
    except Exception as e:
        err_msg = f"GitHub issue retrieval error: {str(e)}"
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
    user_req = state.get("user_request", "").lower()
    target_num = intent.get("target_issue_number")
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    analyzed = []
    actionable = []

    # 1. Triage existing GitHub issues if present
    for issue in raw_issues:
        result = triage_issue(issue)
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

    # 2. Autonomous Code Defect Scan:
    # Scan the complete repository across all files to find ALL latent errors and issues
    is_sweep_requested = any(w in user_req for w in ["all", "errors", "bugs", "sweep", "complete", "completely", "scan"])
    should_scan_code = (not actionable or is_sweep_requested) and (intent.get("needs_code_fix", False) or intent.get("needs_code_analysis", False) or is_sweep_requested) and not target_num

    if should_scan_code:
        decisions.append(f"Scanning complete codebase files in `{owner}/{repo}` for latent bugs and security vulnerabilities.")

        # Retrieve file list — this can fail (rate limit, auth, not found). Do NOT continue with fake data.
        try:
            repo_files = client.list_repository_files(owner=owner, repo=repo)
        except RuntimeError as list_err:
            err_msg = str(list_err)
            logger.error(f"[AGENT] Repository file listing failed for {owner}/{repo}: {err_msg}")
            errors.append(f"Repository inspection failed: {err_msg}")
            decisions.append(f"Repository inspection failed for `{owner}/{repo}`: {err_msg}")
            actions.append("Repository file listing failed — code scan skipped.")
            return {
                "analyzed_issues": analyzed,
                "actionable_issues": actionable,
                "decisions": decisions,
                "actions_taken": actions,
                "errors": errors,
                "can_proceed": False,
            }

        scan_idx = 1
        for fpath in repo_files:
            try:
                f_res = client.get_repository_file(owner=owner, repo=repo, path=fpath)
                raw_text = f_res.get("raw_text") or ""
                if not raw_text and "content" in f_res:
                    raw_text = base64.b64decode(f_res["content"]).decode("utf-8", errors="ignore")

                # Scan for ALL defects in file
                file_defects = scan_all_defects_in_code(fpath, raw_text, all_repo_files=repo_files)
                for defect in file_defects:
                    # Avoid duplicate issue if already in actionable for same file & defect_type
                    if any(a.get("file_path") == fpath and a.get("defect_type") == defect["defect_type"] for a in actionable):
                        continue

                    is_act = defect["severity"] in ("CRITICAL", "HIGH", "MEDIUM")
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
                        "cwe": defect.get("cwe"),
                        "lineno": defect.get("lineno"),
                        "snippet": defect.get("snippet"),
                        "defect_type": defect.get("defect_type"),
                        "jira_ticket_key": None,
                        "pull_request_number": None,
                    }
                    analyzed.append(defect_item)
                    if is_act:
                        actionable.append(defect_item)
                        actions.append(f"Code scanner detected defect {defect['cwe']} in `{fpath}` (line {defect.get('lineno', 1)}): {defect['title']}.")
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
        "errors": errors,
    }


def inspect_code_node(state: DevPilotState) -> dict[str, Any]:
    """Execute Swytchcode github.content.get to read target source files."""
    actionable = state.get("actionable_issues", [])
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))
    inspected_files = []

    fetched_files: dict[str, dict[str, Any]] = {}
    for issue in actionable:
        file_path = issue.get("file_path", "src/services/payment_service.py")
        if file_path not in fetched_files:
            decisions.append(f"Inspecting codebase: reading `{file_path}` for issue #{issue['number']}.")
            try:
                file_res = client.get_repository_file(owner=owner, repo=repo, path=file_path)
                raw_content = file_res.get("raw_text")
                if not raw_content and "content" in file_res:
                    raw_content = base64.b64decode(file_res["content"]).decode("utf-8", errors="ignore")
                fetched_files[file_path] = {
                    "path": file_path,
                    "content": raw_content or "",
                    "sha": file_res.get("sha", ""),
                }
                actions.append(f"Read codebase file `{file_path}` ({len(raw_content or '')} chars) via Swytchcode/filesystem.")
            except Exception as e:
                err_msg = f"Failed to inspect code file `{file_path}`: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)

        if file_path in fetched_files:
            inspected_files.append({
                "path": file_path,
                "github_issue_number": issue["number"],
                "content": fetched_files[file_path]["content"],
                "sha": fetched_files[file_path]["sha"],
            })

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
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))

    file_map = {f["path"]: f["content"] for f in inspected_files}
    initial_code_map = dict(file_map)
    patches = []

    for issue in actionable:
        issue_num = issue["number"]
        fpath = issue.get("file_path", "")
        current_code = file_map.get(fpath) or next((f["content"] for f in inspected_files if f.get("github_issue_number") == issue_num), "")
        original_baseline = initial_code_map.get(fpath, current_code)

        if not issue.get("lineno") or not issue.get("snippet"):
            detected = scan_code_for_defects(fpath, current_code)
            if detected:
                issue["lineno"] = detected.get("lineno")
                issue["snippet"] = detected.get("snippet")
                if not issue.get("cwe"):
                    issue["cwe"] = detected.get("cwe")

        patch_info = diagnose_and_generate_patch(issue, current_code)
        file_map[fpath] = patch_info["fixed_code"]

        # Ensure unified diff compares from original baseline
        if original_baseline != patch_info["fixed_code"]:
            import difflib
            orig_lines = original_baseline.splitlines(keepends=True)
            fixed_lines = patch_info["fixed_code"].splitlines(keepends=True)
            patch_info["diff"] = "\n".join(difflib.unified_diff(orig_lines, fixed_lines, fromfile=f"a/{fpath}", tofile=f"b/{fpath}", lineterm=""))
            patch_info["original_code"] = original_baseline

        # Carry over SHA if available
        matched_inspected = next((f for f in inspected_files if f["path"] == fpath), None)
        if matched_inspected and matched_inspected.get("sha"):
            patch_info["sha"] = matched_inspected["sha"]

        patches.append(patch_info)
        decisions.append(
            f"Code solution planned for #{issue_num} (`{patch_info['file_path']}`): {patch_info['explanation']}"
        )
        actions.append(f"Generated unified diff patch for `{patch_info['file_path']}`.")

    return {
        "code_patches": patches,
        "decisions": decisions,
        "actions_taken": actions,
    }


def modify_code_node(state: DevPilotState) -> dict[str, Any]:
    """Apply generated code patches to actual repository files."""
    patches = state.get("code_patches", [])
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    repo_dir = client._find_repository_directory(owner, repo)

    # Consolidate latest patch per file
    latest_patches = {}
    for p in patches:
        latest_patches[p["file_path"]] = p

    for file_path, patch in latest_patches.items():
        fixed_code = patch["fixed_code"]
        commit_msg = f"fix: resolve {patch.get('cwe', 'defect')} in {file_path}"

        if repo_dir and os.path.isdir(repo_dir):
            decisions.append(f"Modifying local repository code file `{file_path}` ({len(fixed_code)} bytes).")
            try:
                client.update_repository_file(
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    content=fixed_code,
                    message=commit_msg,
                    branch="main",
                )
                actions.append(f"Modified real code in `{file_path}` on local disk.")
            except Exception as e:
                err_msg = f"Failed to modify local code file `{file_path}`: {e}"
                logger.error(err_msg)
                errors.append(err_msg)
        else:
            # Remote-only repo: stage for commit directly to feature branch in commit_changes_node
            decisions.append(f"Prepared patch for remote file `{file_path}` (staged for feature branch commit).")
            actions.append(f"Staged patch for `{file_path}` for remote branch commit.")

    return {
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def run_tests_node(state: DevPilotState) -> dict[str, Any]:
    """Execute repository automated test suite (pytest) as a hard safety gate."""
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")
    actionable = state.get("actionable_issues", [])

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    test_path = None
    for issue in actionable:
        if issue.get("test_path"):
            test_path = issue.get("test_path")
            break

    test_res = client.run_tests(owner=owner, repo=repo, test_path=test_path)
    passed = test_res.get("passed", False)
    status = test_res.get("status", "TEST FAILED")

    if passed:
        decisions.append(f"Safety Gate PASSED: {status} ({test_res.get('summary')}). All automated regression assertions succeeded.")
        actions.append(f"Executed automated test suite ({test_res.get('command')}): PASSED ({test_res.get('summary')}, exit code {test_res.get('exit_code')}). Proceeding to Git branch & commit.")
        can_proceed = True
    elif status == "NOT_AVAILABLE":
        decisions.append(f"Safety Gate ADVISORY: {test_res.get('summary')} Proceeding with feature branch and Pull Request for senior review.")
        actions.append(f"Test suite not available for remote repo ({test_res.get('summary')}). Proceeding to feature branch and Pull Request.")
        can_proceed = True
    else:
        decisions.append(f"Safety Gate BLOCKED: {status} ({test_res.get('summary')}). Halting downstream Git branch creation, commit, and Pull Request.")
        actions.append(f"Executed automated test suite ({test_res.get('command')}): FAILED ({test_res.get('summary')}, exit code {test_res.get('exit_code')}). Halting workflow.")
        errors.append(f"Test suite failure ({test_res.get('status')}): {test_res.get('summary')}")
        can_proceed = False


    return {
        "test_results": test_res,
        "can_proceed": can_proceed,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def create_git_branch_node(state: DevPilotState) -> dict[str, Any]:
    """Create a dedicated real Git feature branch for the verified fix."""
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")
    github_user = state.get("github_username") or os.getenv("GITHUB_USERNAME", "nikhil-mutreja")
    actionable = state.get("actionable_issues", [])

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    target_issue = actionable[0] if actionable else {}
    issue_num = target_issue.get("number", 1)
    fpath = target_issue.get("file_path", "fix")
    base_name = os.path.basename(fpath).split(".")[0]
    branch_name = f"fix/{github_user}-gh-{issue_num}-{base_name}"

    decisions.append(f"Creating Git branch `{branch_name}` from `main`.")
    try:
        res = client.create_git_branch(owner=owner, repo=repo, branch_name=branch_name, base_branch="main")
        actions.append(f"Created real Git branch `{branch_name}`.")
        return {
            "git_branch": branch_name,
            "decisions": decisions,
            "actions_taken": actions,
            "errors": errors,
        }
    except Exception as e:
        err_msg = f"Failed to create git branch `{branch_name}`: {e}"
        logger.error(err_msg)
        errors.append(err_msg)
        return {
            "git_branch": branch_name,
            "decisions": decisions,
            "actions_taken": actions,
            "errors": errors,
        }


def commit_changes_node(state: DevPilotState) -> dict[str, Any]:
    """Commit staged code modifications to real Git repository or remote feature branch."""
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")
    github_user = state.get("github_username") or os.getenv("GITHUB_USERNAME", "nikhil-mutreja")
    patches = state.get("code_patches", [])
    branch_name = state.get("git_branch", f"fix/{github_user}-patch")

    client = SwytchcodeClient(mode=mode)
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))

    commit_sha = ""
    # Consolidate latest patch per file to commit each file once
    latest_patches = {}
    for p in patches:
        latest_patches[p["file_path"]] = p

    for file_path, patch in latest_patches.items():
        commit_msg = f"fix: resolve {patch.get('cwe', 'defect')} in {file_path} by @{github_user}"
        fixed_code = patch.get("fixed_code", "")
        file_sha = patch.get("sha")
        try:
            c_res = client.commit_changes(
                owner=owner,
                repo=repo,
                file_path=file_path,
                message=commit_msg,
                branch_name=branch_name,
                content=fixed_code,
                sha=file_sha,
            )
            commit_sha = c_res.get("commit_sha", "") or (c_res.get("commit", {}) or {}).get("sha", "") or (c_res.get("data", {}).get("commit", {}) or {}).get("sha", "")
            decisions.append(f"Committed changes on `{branch_name}` for `{file_path}`: SHA `{commit_sha}`.")
            actions.append(f"Created real Git commit `{commit_sha[:8] if commit_sha else 'HEAD'}`: '{commit_msg}'.")
        except Exception as e:
            err_msg = f"Failed to commit changes for `{file_path}`: {e}"
            logger.error(err_msg)
            errors.append(err_msg)

    return {
        "commit_sha": commit_sha,
        "decisions": decisions,
        "actions_taken": actions,
        "errors": errors,
    }


def create_pull_request_node(state: DevPilotState) -> dict[str, Any]:
    """Open GitHub Pull Request via Swytchcode for Senior Review."""
    patches = state.get("code_patches", [])
    actionable = state.get("actionable_issues", [])
    owner = state.get("repo_owner") or os.getenv("GITHUB_REPO_OWNER", "octocat")
    repo = state.get("repo_name") or os.getenv("GITHUB_REPO_NAME", "Hello-World")
    mode = state.get("app_mode") or os.getenv("APP_MODE", "mock")
    branch_name = state.get("git_branch", "fix-branch")
    commit_sha = state.get("commit_sha", "")

    client = SwytchcodeClient(mode=mode)
    github_user = state.get("github_username") or os.getenv("GITHUB_USERNAME", "nikhil-mutreja")
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))
    pull_requests = []
    pr_error = None

    for patch in patches:
        issue_num = patch["github_issue_number"]
        file_path = patch["file_path"]

        # In real mode, if a PR was already created for this feature branch on GitHub, link to it
        if not client.is_mock() and pull_requests:
            existing_pr = pull_requests[0]
            existing_num = existing_pr.get("number") or existing_pr.get("data", {}).get("number")
            for issue in actionable:
                if issue["number"] == issue_num:
                    issue["pull_request_number"] = existing_num
            continue

        pr_title = f"[Senior Review Requested] Resolve #{issue_num}: Fix {patch.get('cwe', 'Bug')} in {os.path.basename(file_path)} (@{github_user})"

        checklist_items = patch.get("review_checklist", [
            "Functional correctness: automated patch resolves defect without functional regression.",
            "Automated test verification: all pytest suites passed locally prior to PR submission.",
            "Security audit: confirmed no credential exposure or arbitrary injection vectors.",
            "Boundary conditions: validated zero/null/empty/whitespace input handling.",
            "Backward compatibility: all public module exports and interfaces maintained.",
        ])
        checklist_md = "\n".join(f"- [ ] {item}" for item in checklist_items)

        # Build comprehensive defect breakdown across all patches
        defect_breakdown = []
        for p in patches:
            defect_breakdown.append(
                f"- **Defect #{p['github_issue_number']}** (`{p['file_path']}`, line {p.get('lineno', 1)}): "
                f"`{p.get('cwe', 'CWE-DEFECT')}` — {p['explanation']}"
            )
        breakdown_md = "\n".join(defect_breakdown) if defect_breakdown else f"- `{patch.get('cwe', 'CWE-DEFECT')}` in `{file_path}`"

        diffs_md = "\n\n".join(
            f"**File: `{p['file_path']}`**\n```diff\n{p['diff']}\n```"
            for p in patches if p.get("diff")
        ) or f"```diff\n{patch['diff']}\n```"

        pr_body = (
            f"### 🚀 Senior Engineer Review Request\n\n"
            f"> **Submitted by:** @{github_user} via DevPilot Autonomous AI Software Engineer\n"
            f"> **Target Repository:** `{owner}/{repo}` | **Branch:** `{branch_name}` → `main`\n"
            f"> **Target Defect / Issue:** #{issue_num} | **Commit SHA:** `{commit_sha[:8] if commit_sha else 'HEAD'}`\n"
            f"> **Total Actionable Issues Resolved:** {len(actionable)}\n"
            f"> **Review Status:** 🟡 Pending Senior Engineer Approval\n\n"
            f"#### 🔍 Defect Triage & Root Cause Analysis\n"
            f"{breakdown_md}\n\n"
            f"#### 🛠️ Unified Code Diff(s)\n"
            f"{diffs_md}\n\n"
            f"#### 📋 Senior Engineer Sign-Off Checklist\n"
            f"{checklist_md}\n\n"
            f"---\n"
            f"*Generated autonomously by DevPilot AI Software Engineer for Senior Reviewers. Contributed by @{github_user}.*"
        )

        try:
            pr_res = client.create_pull_request(
                owner=owner,
                repo=repo,
                title=pr_title,
                head=branch_name,
                base="main",
                body=pr_body,
                author=github_user,
            )

            # Validate that the response is actually a successful PR object
            is_error = False
            err_reason = ""
            if isinstance(pr_res, dict):
                inner_data = pr_res.get("data", {})
                if isinstance(inner_data, dict) and inner_data.get("status") in ("404", "403", "422", 404, 403, 422):
                    is_error = True
                    err_reason = inner_data.get("message", "GitHub API error")
                elif "error" in pr_res:
                    is_error = True
                    err_reason = str(pr_res.get("error"))
                elif not pr_res.get("number") and not pr_res.get("id") and not inner_data.get("number"):
                    is_error = True
                    err_reason = pr_res.get("message") or inner_data.get("message") or "No PR number returned"

            if is_error:
                raise RuntimeError(err_reason)

            pr_num = pr_res.get("number") or pr_res.get("data", {}).get("number")
            pr_res["review_checklist"] = checklist_items
            pr_res["cwe"] = patch.get("cwe")
            pr_res["lineno"] = patch.get("lineno")
            pr_res["snippet"] = patch.get("snippet")
            pr_res["explanation"] = patch.get("explanation")
            pr_res["diff"] = patch.get("diff")
            pr_res["file_path"] = file_path
            pr_res["author"] = github_user
            pr_res["body"] = pr_body
            pull_requests.append(pr_res)

            for issue in actionable:
                if issue["number"] == issue_num:
                    issue["pull_request_number"] = pr_num

            decisions.append(f"Pull request #{pr_num} opened by @{github_user} on branch `{branch_name}` for Senior Engineer review.")
            actions.append(f"Created GitHub Pull Request #{pr_num} by @{github_user}: '{pr_title}'.")
        except Exception as e:
            pr_error = str(e)
            logger.warning(f"Remote GitHub Pull Request creation could not be completed: {pr_error}")
            errors.append(f"Remote Pull Request creation restricted/failed: {pr_error}")
            actions.append(f"Attempted GitHub Pull Request creation via Swytchcode tool github.pull.create: {pr_error}")
            decisions.append(f"Remote PR creation failed ({pr_error}). Real branch `{branch_name}` and commit `{commit_sha[:8] if commit_sha else 'HEAD'}` preserved locally.")


    return {
        "actionable_issues": actionable,
        "pull_requests": pull_requests,
        "pr_error": pr_error,
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
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))
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
            ticket_key = res.get("key")
            issue["jira_ticket_key"] = ticket_key
            jira_results.append(res)
            actions.append(f"Jira task created: `{ticket_key}` for GitHub #{issue_num}.")
        except Exception as e:
            err_msg = f"Jira integration not configured / failed: {str(e)}"
            logger.info(err_msg)
            errors.append(err_msg)
            actions.append(f"Jira task creation skipped: {str(e)}.")
            decisions.append(f"Jira integration unconfigured: payload preserved for `{project_key}`.")
            jira_results.append({
                "status": "NOT_CONFIGURED",
                "key": "N/A",
                "summary": summary,
                "error": str(e),
                "intended_payload": desc,
            })

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
    decisions = list(state.get("decisions", []))
    actions = list(state.get("actions_taken", []))
    errors = list(state.get("errors", []))
    slack_results = []

    decisions.append(f"Slack selected: notifying channel `{channel}` of engineering updates.")
    message_text = format_slack_message(jira_results, actionable, pull_requests, repo_name)

    try:
        res = client.send_slack_message(channel=channel, text=message_text)
        slack_results.append(res)
        actions.append(f"Slack notification dispatched to channel `{channel}`.")
    except Exception as e:
        err_msg = f"Slack notification not configured / failed: {str(e)}"
        logger.info(err_msg)
        errors.append(err_msg)
        actions.append(f"Slack notification skipped: {str(e)}.")
        decisions.append(f"Slack integration unconfigured: message payload preserved for `{channel}`.")
        slack_results.append({
            "status": "NOT_CONFIGURED",
            "channel": channel,
            "error": str(e),
            "intended_message": message_text,
        })

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
    mode = state.get("app_mode", "mock").upper()
    owner = state.get("repo_owner", "")
    repo = state.get("repo_name", "")
    github_user = state.get("github_username", "nikhil-mutreja")
    analyzed = state.get("analyzed_issues", [])
    actionable = state.get("actionable_issues", [])
    patches = state.get("code_patches", [])
    test_results = state.get("test_results", {})
    git_branch = state.get("git_branch", "")
    commit_sha = state.get("commit_sha", "")
    pull_requests = state.get("pull_requests", [])
    pr_error = state.get("pr_error")
    jira_results = state.get("jira_results", [])
    slack_results = state.get("slack_results", [])
    errors = state.get("errors", [])
    decisions = state.get("decisions", [])
    actions = state.get("actions_taken", [])

    lines = []
    mode_badge = "🟢 **REAL MODE (Live Execution with Real Git & Swytchcode)**" if mode in ("REAL", "PRODUCTION") else "🟡 **MOCK / DEMO MODE (Simulated Sandbox)**"
    lines.append(f"### DevPilot Autonomous AI Software Engineer Report")
    lines.append(f"> {mode_badge}")
    lines.append(f"> **Target Repository:** `{owner}/{repo}` | **Contributor:** `@{github_user}` | **Task:** `{task_type}`\n")

    # Executive Summary
    lines.append("#### 📊 Executive Summary")
    lines.append(f"- **Issues Triaged:** {len(analyzed)}")
    lines.append(f"- **Actionable Issues Identified:** {len(actionable)}")
    lines.append(f"- **Code Patches Applied:** {len(patches)}")
    
    test_status = test_results.get("status", "N/A")
    lines.append(f"- **Automated Test Gate:** `{test_status}` ({test_results.get('summary', 'No tests run')})")
    
    if git_branch:
        lines.append(f"- **Git Branch Created:** `{git_branch}`")
    if commit_sha:
        lines.append(f"- **Git Commit SHA:** `{commit_sha}`")
    if pull_requests:
        lines.append(f"- **Pull Requests Opened:** {len(pull_requests)}")
    elif pr_error:
        lines.append(f"- **Pull Request Status:** ⚠️ Remote creation blocked (`{pr_error[:80]}...`)")
    else:
        lines.append(f"- **Pull Requests Opened:** 0")

    # Automated Test Execution Details
    if test_results and test_results.get("status") != "N/A":
        lines.append("\n#### 🧪 Automated Test Execution (Safety Gate)")
        lines.append(f"- **Runner Command:** `{test_results.get('command', 'pytest -v')}`")
        lines.append(f"- **Status:** **{test_results.get('status')}** (Exit Code: `{test_results.get('exit_code')}`)")
        lines.append(f"- **Summary:** {test_results.get('summary')}")
        if test_results.get("stdout"):
            lines.append("```text")
            stdout_lines = test_results["stdout"].strip().splitlines()
            # Show summary section of test runner
            snippet = "\n".join(stdout_lines[:25])
            if len(stdout_lines) > 25:
                snippet += f"\n... [{len(stdout_lines) - 25} lines truncated]"
            lines.append(snippet)
            lines.append("```")

    # Code Diffs
    if patches:
        lines.append("\n#### 💻 Code Patches & Pull Requests")
        for patch in patches:
            pr_info = ""
            for pr in pull_requests:
                if f"#{patch['github_issue_number']}" in pr.get("title", ""):
                    pr_info = f" | **PR:** [{pr.get('title')}]({pr.get('html_url')})"
            lines.append(f"**Target File:** `{patch['file_path']}` (Issue #{patch['github_issue_number']}){pr_info}")
            lines.append(f"*{patch['explanation']}*\n")
            lines.append(f"```diff\n{patch['diff']}\n```\n")

    # Pull Request / Senior Review
    if pull_requests:
        lines.append("#### 👨‍💻 Senior Engineer Review Ready Pull Requests")
        for pr in pull_requests:
            lines.append(f"- **{pr.get('title')}** -> [Review PR #{pr.get('number')}]({pr.get('html_url')})")
            lines.append(f"  - **Contributor / Author:** `@{pr.get('author', github_user)}`")
            lines.append(f"  - **Target Branch:** `{pr.get('head', {}).get('ref', git_branch)}` -> `main`")
            if pr.get("cwe"):
                lines.append(f"  - **Defect Class & Location:** `{pr.get('cwe')}` in `{pr.get('file_path')}` (Line {pr.get('lineno', 1)})")
            lines.append(f"  - **Review Status:** 🟡 `Pending Senior Engineer Sign-Off`")
        lines.append("")
    elif pr_error:
        lines.append("#### 👨‍💻 Pull Request Status")
        lines.append(f"> ⚠️ **Remote PR Submission Note:** The code was modified, tested, branched (`{git_branch}`), and committed (`{commit_sha[:8] if commit_sha else 'HEAD'}`) locally.")
        lines.append(f"> Remote GitHub API reported: `{pr_error}`")
        lines.append(f"> Per DevPilot transparency principles, fake PR numbers are never generated.\n")

    # Traceability Matrix
    if actionable:
        lines.append("#### 🔗 Complete Software Engineering Traceability")
        lines.append("| GitHub Issue | Severity | Test Gate | Git Branch | Commit SHA | Pull Request | Jira Task | Slack Alert |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for item in actionable:
            gh_link = f"#{item['number']}"
            sev = item["severity"]
            t_gate = "✅ Passed" if test_results.get("passed") else ("❌ Failed" if "FAILED" in test_results.get("status", "") else "—")
            b_name = f"`{git_branch}`" if git_branch else "—"
            c_sha = f"`{commit_sha[:7]}`" if commit_sha else "—"
            pr_num = item.get("pull_request_number")
            pr_display = f"`PR #{pr_num}`" if pr_num else ("⚠️ Blocked" if pr_error else "—")
            jira_key = item.get("jira_ticket_key") or ("Intended" if jira_results else "—")
            slack_status = "Dispatched" if any(s.get("delivered", False) for s in slack_results) else ("Intended" if slack_results else "—")
            lines.append(f"| {gh_link} | **{sev}** | {t_gate} | {b_name} | {c_sha} | {pr_display} | `{jira_key}` | {slack_status} |")

    # Warnings / Errors Encountered
    if errors:
        lines.append("\n#### ⚠️ Execution Diagnostics & Notices")
        for err in errors:
            lines.append(f"- {err}")

    # Decisions & Actions Audit Trail
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

    if intent.get("investigate_only", False):
        should_jira, _ = should_create_jira(intent, actionable)
        if should_jira:
            return "create_jira"
        should_slack, _ = should_send_slack(intent, [], actionable, [])
        if should_slack:
            return "send_slack"
        return "synthesize_response"

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
    """Route to modify_code if patches were generated."""
    patches = state.get("code_patches", [])
    if patches:
        return "modify_code"
    return "synthesize_response"


def route_after_run_tests(state: DevPilotState) -> str:
    """Safety gate routing: halt if tests failed; proceed to branching if passed."""
    can_proceed = state.get("can_proceed", False)
    intent = state.get("intent", {})
    actionable = state.get("actionable_issues", [])

    if not can_proceed:
        logger.warning("[SAFETY GATE] Automated tests failed. Halting Git branch and PR operations.")
        should_jira, _ = should_create_jira(intent, actionable)
        if should_jira:
            return "create_jira"
        should_slack, _ = should_send_slack(intent, [], actionable, [])
        if should_slack:
            return "send_slack"
        return "synthesize_response"

    # Tests passed: proceed to branch creation if PR requested
    if intent.get("needs_pr", False):
        return "create_git_branch"

    should_jira, _ = should_create_jira(intent, actionable)
    if should_jira:
        return "create_jira"

    should_slack, _ = should_send_slack(intent, [], actionable, [])
    if should_slack:
        return "send_slack"

    return "synthesize_response"


def route_after_commit_changes(state: DevPilotState) -> str:
    """Route after commit to create_pull_request, Jira, Slack, or final response."""
    intent = state.get("intent", {})
    actionable = state.get("actionable_issues", [])

    if intent.get("needs_pr", False):
        return "create_pull_request"

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
    workflow.add_node("modify_code", modify_code_node)
    workflow.add_node("run_tests", run_tests_node)
    workflow.add_node("create_git_branch", create_git_branch_node)
    workflow.add_node("commit_changes", commit_changes_node)
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
            "modify_code": "modify_code",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_edge("modify_code", "run_tests")

    workflow.add_conditional_edges(
        "run_tests",
        route_after_run_tests,
        {
            "create_git_branch": "create_git_branch",
            "create_jira": "create_jira",
            "send_slack": "send_slack",
            "synthesize_response": "synthesize_response",
        },
    )

    workflow.add_edge("create_git_branch", "commit_changes")

    workflow.add_conditional_edges(
        "commit_changes",
        route_after_commit_changes,
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
    github_username: str = "nikhil-mutreja",
    jira_project: str = "DEV",
    slack_channel: str = "#dev-alerts",
    app_mode: str = "mock",
    **kwargs: Any,
) -> DevPilotState:
    """Execute the complete DevPilot LangGraph workflow."""
    app = build_devpilot_graph()

    resolved_username = kwargs.get("github_username") or github_username or os.getenv("GITHUB_USERNAME", "nikhil-mutreja")

    initial_state: DevPilotState = {
        "user_request": user_request,
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "github_username": resolved_username,
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
        "test_results": {},
        "git_branch": "",
        "commit_sha": "",
        "patch_plan": {},
        "pr_error": None,
        "can_proceed": True,
        "final_response": "",
    }

    final_state = app.invoke(initial_state)
    return final_state
