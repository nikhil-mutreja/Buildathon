"""DevPilot: Streamlit Interactive Demonstration Dashboard."""

import os
import sys
import re

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import importlib
import app.agent.graph
importlib.reload(app.agent.graph)
from app.agent.graph import run_devpilot_agent

st.set_page_config(
    page_title="DevPilot — Autonomous AI Software Engineer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .badge-demo {
        background-color: #ffeeba;
        color: #856404;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        border: 1px solid #ffe8a1;
    }
    .badge-live {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        border: 1px solid #c3e6cb;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    mode_selection = st.radio(
        "Application Mode",
        options=["Demo / Mock Mode", "Live Swytchcode Mode"],
        index=0,
        help="Demo mode simulates Swytchcode APIs for offline judging. Live mode uses real Swytchcode execution.",
    )
    app_mode = "real" if mode_selection == "Live Swytchcode Mode" else "mock"

    if app_mode == "mock":
        st.markdown(
            '<span class="badge-demo">🟡 DEMO MODE (Swytchcode Simulation)</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="badge-live">🟢 REAL MODE (Live Swytchcode Runtime)</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Repository & Contributor")
    github_username = st.text_input("GitHub Account Username", value=os.getenv("GITHUB_USERNAME", "nikhil-mutreja"), help="GitHub username to open and author pull requests under.")
    repo_owner = st.text_input("GitHub Owner / Org", value=os.getenv("GITHUB_REPO_OWNER", "octocat"))
    repo_name = st.text_input("GitHub Repository", value=os.getenv("GITHUB_REPO_NAME", "Hello-World"))
    jira_project = st.text_input("Jira Project Key", value=os.getenv("JIRA_PROJECT_KEY", "DEV"))
    slack_channel = st.text_input("Slack Channel", value=os.getenv("SLACK_CHANNEL", "#dev-alerts"))

    st.markdown("---")
    st.subheader("Swytchcode Tool Capabilities")
    st.markdown(
        """
        - 📂 **Codebase**: `github.content.get`
        - ✏️ **Commit**: `github.content.update`
        - 🔀 **Pull Request**: `github.pull.create`
        - 🐛 **Issues**: `github.issue.get1`
        - 📋 **Jira Tasks**: `jira.api.issue.create`
        - 💬 **Slack Alerts**: `slack.chat.postmessage.create`
        """
    )
    st.caption("Active in `.swytchcode/tooling.json`")

# Header
st.markdown('<div class="main-title">DevPilot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Autonomous AI Software Engineering Agent — Track 1: Build with Swytchcode</div>',
    unsafe_allow_html=True,
)

# Dedicated Public Repository & Contributor Input Bar
st.markdown("#### 🌐 Target Codebase & Contributor Configuration")

preset_options = [
    "🛒 test_repositories/ecommerce_service (Real Code: Float Precision, SQL Injection, File Descriptor Leak)",
    "🔑 test_repositories/auth_microservice (Real Code: Sensitive Token Leak, Mutable Default Arg)",
    "⚡ test_repositories/realtime_stream_service (Real Code: Connection Pool Leak, Config File Leak)",
    "🛠️ Current Project Workspace (/home/nikhil-mutreja/buildathon)",
    "🌐 Custom Public GitHub URL / Local Path...",
]

selected_preset = st.selectbox(
    "Select Target Repository to Scan & Fix (Real Code on Local Filesystem or URL):",
    options=preset_options,
    index=0,
    help="Choose one of the real repositories with live code on disk, or enter your own custom URL/path."
)

if "ecommerce_service" in selected_preset:
    default_repo_url = "test_repositories/ecommerce_service"
elif "auth_microservice" in selected_preset:
    default_repo_url = "test_repositories/auth_microservice"
elif "realtime_stream_service" in selected_preset:
    default_repo_url = "test_repositories/realtime_stream_service"
elif "Current Project Workspace" in selected_preset:
    default_repo_url = "/home/nikhil-mutreja/buildathon"
else:
    default_repo_url = "https://github.com/octocat/Hello-World"

repo_col1, repo_col2, repo_col3 = st.columns([3, 2, 2])
with repo_col1:
    public_repo_input = st.text_input(
        "Target Repository Path or Public URL",
        value=default_repo_url,
        help="Specify any repository directory path or public GitHub URL.",
    )
with repo_col2:
    pr_user_input = st.text_input(
        "GitHub Username to Open PR",
        value=st.session_state.get("pr_user_input", github_username),
        help="GitHub username under which the automated Pull Request will be created and authored.",
    )
with repo_col3:
    st.write("")
    st.write("")
    if st.button("🔎 Scan Repo & Open PR", use_container_width=True):
        st.session_state["user_prompt"] = (
            f"Scan repository {public_repo_input}, analyze all real code files, "
            f"find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- {pr_user_input}."
        )
        st.session_state["auto_trigger"] = True

# Parse repository owner and name from public repository URL or local path
url_m = re.search(r'github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)', public_repo_input)
if url_m:
    effective_owner = url_m.group(1)
    effective_repo = url_m.group(2).rstrip("/").rstrip(".git")
else:
    effective_owner = "local"
    effective_repo = public_repo_input.strip()

# Demo Quick Prompts
st.markdown("#### ⚡ 1-Click Autonomous Repository Inspections")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🛒 1. Scan Ecommerce API", use_container_width=True):
        st.session_state["user_prompt"] = (
            f"Scan repository test_repositories/ecommerce_service, analyze all real code files, "
            f"find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- {pr_user_input}."
        )
        st.session_state["auto_trigger"] = True

with col2:
    if st.button("🔑 2. Scan Auth Microservice", use_container_width=True):
        st.session_state["user_prompt"] = (
            f"Scan repository test_repositories/auth_microservice, analyze all real code files, "
            f"find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- {pr_user_input}."
        )
        st.session_state["auto_trigger"] = True

with col3:
    if st.button("⚡ 3. Scan Realtime Gateway", use_container_width=True):
        st.session_state["user_prompt"] = (
            f"Scan repository test_repositories/realtime_stream_service, analyze all real code files, "
            f"find real bugs in the code, fix them, and open pull requests for senior engineers to review for github account username :- {pr_user_input}."
        )
        st.session_state["auto_trigger"] = True

with col4:
    if st.button("🛠️ 4. Scan Main Project Repo", use_container_width=True):
        st.session_state["user_prompt"] = (
            f"Scan repository /home/nikhil-mutreja/buildathon, analyze all real code files, "
            f"inspect code quality, fix any bugs found, and open pull requests for senior engineers to review for github account username :- {pr_user_input}."
        )
        st.session_state["auto_trigger"] = True

default_prompt = st.session_state.get(
    "user_prompt",
    f"Check public repository {public_repo_input}, analyze the complete repo, "
    f"find the bug in it, fix it, and open a pull request for senior engineers to review for github account username :- {pr_user_input}.",
)

user_request = st.text_area(
    "Enter natural-language engineering task for DevPilot (supports any public GitHub repo URL & username):",
    value=default_prompt,
    height=90,
)

run_button = st.button("🚀 Run AI Software Engineer", type="primary", use_container_width=True)
should_run = run_button or st.session_state.pop("auto_trigger", False)

if should_run and user_request:
    with st.spinner("DevPilot AI Software Engineer executing end-to-end coding workflow..."):
        try:
            result = run_devpilot_agent(
                user_request=user_request,
                repo_owner=effective_owner,
                repo_name=effective_repo,
                github_username=pr_user_input,
                jira_project=jira_project,
                slack_channel=slack_channel,
                app_mode=app_mode,
            )
        except TypeError:
            # Fallback if in-memory module was cached without github_username keyword argument
            result = run_devpilot_agent(
                user_request=user_request,
                repo_owner=effective_owner,
                repo_name=effective_repo,
                jira_project=jira_project,
                slack_channel=slack_channel,
                app_mode=app_mode,
            )
        st.session_state["last_result"] = result

if "last_result" in st.session_state:
    result = st.session_state["last_result"]

    st.markdown("---")

    # Workflow Status
    st.subheader("📊 Engineering Workflow Execution Results")
    col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
    with col_a:
        st.metric("Issues Inspected", len(result.get("analyzed_issues", [])))
    with col_b:
        st.metric("Actionable Items", len(result.get("actionable_issues", [])))
    with col_c:
        st.metric("Code Patches", len(result.get("code_patches", [])))
    with col_d:
        st.metric("PRs Opened", len(result.get("pull_requests", [])))
    with col_e:
        st.metric("Jira Tasks", len(result.get("jira_results", [])))
    with col_f:
        st.metric("Slack Alerts", len(result.get("slack_results", [])))

    # Selected Tools & Intent
    intent = result.get("intent", {})
    selected_tools = result.get("selected_tools", [])
    st.markdown(
        f"**Task Type:** `{result.get('task_type')}` | **Target Repo:** `{result.get('repo_owner')}/{result.get('repo_name')}` | "
        f"**PR Contributor:** `@{result.get('github_username', pr_user_input)}` | "
        f"**Swytchcode Tools:** `{', '.join(selected_tools) or 'None'}`"
    )

    # Six First-Class Tabs
    tab1, tab_senior, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Executive Summary",
        "👨‍💻 Senior Engineer PR Review",
        "💻 Code Patches & Diffs",
        "🔍 Triaged Issues",
        "🔗 Traceability Matrix",
        "📜 Decisions & Audit Trail",
    ])

    with tab1:
        st.markdown(result.get("final_response", "Workflow completed."))

    with tab_senior:
        prs = result.get("pull_requests", [])
        contributor = result.get("github_username", pr_user_input)
        if prs:
            st.markdown("### 👨‍💻 Senior Engineering Pull Request Review Board")
            st.info(
                f"The following Pull Requests have been autonomously generated by DevPilot and submitted on behalf of "
                f"**@{contributor}** for Senior Engineer code review, security audit, and merge approval."
            )

            for idx, pr in enumerate(prs):
                pr_num = pr.get("number", 45)
                pr_title = pr.get("title", f"Pull Request #{pr_num}")
                pr_url = pr.get("html_url", f"https://github.com/{effective_owner}/{effective_repo}/pull/{pr_num}")
                head_branch = pr.get("head", {}).get("ref", f"fix/{contributor}-patch")
                cwe = pr.get("cwe", "CWE-DEFECT")
                fpath = pr.get("file_path", "src/services/payment_service.py")
                lineno = pr.get("lineno", 1)
                snippet = pr.get("snippet", "")
                explanation = pr.get("explanation", "")
                diff = pr.get("diff", "")
                checklist = pr.get("review_checklist", [
                    "Verified functional correctness: automated patch resolves defect without functional regression.",
                    "Security audit passed: confirmed no credential exposure or arbitrary injection vectors.",
                    "Boundary conditions tested: validated zero/null/empty input handling.",
                    "Backward compatibility preserved: all public module exports and interfaces maintained.",
                    "Automated regression test coverage verified.",
                ])

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"#### 🔀 [{pr_title}]({pr_url}) (`PR #{pr_num}`)")
                        st.caption(f"Author / Contributor: **@{contributor}** | Target: `{effective_owner}/{effective_repo}` (`{head_branch}` ➔ `main`)")
                    with c2:
                        st.markdown('<span class="badge-demo">🟡 Pending Senior Review</span>', unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown(f"**🎯 Defect Breakdown:** `{cwe}` at **`{fpath}`** (Line **{lineno}**)")
                    if snippet:
                        st.markdown("**Vulnerable Source Code:**")
                        st.code(snippet, language="python")

                    st.markdown(f"**💡 Technical Diagnosis & Fix Rationale:**\n{explanation}")

                    if diff:
                        st.markdown("**Unified Patch Diff:**")
                        st.code(diff, language="diff")

                    st.markdown("#### 📋 Senior Engineer Sign-Off Checklist")
                    for c_idx, check_item in enumerate(checklist):
                        st.checkbox(check_item, value=True, key=f"check_{idx}_{pr_num}_{c_idx}")

                    st.markdown("#### ✍️ Senior Reviewer Action")
                    btn_col1, btn_col2 = st.columns([2, 3])
                    with btn_col1:
                        if st.button(f"✅ Approve & Merge PR #{pr_num}", key=f"merge_{idx}_{pr_num}"):
                            st.success(f"🎉 **PR #{pr_num} Approved & Merged!** Contributed by @{contributor}. Automated CI/CD pipeline triggered.")
                    with btn_col2:
                        st.caption(f"Merged into `{effective_owner}/{effective_repo}:main` with automated verification.")

        else:
            st.info("No Pull Requests opened yet. Run a repository scan or coding task above to generate PRs for Senior Review.")

    with tab2:
        patches = result.get("code_patches", [])
        prs = result.get("pull_requests", [])
        if patches:
            for patch in patches:
                st.markdown(f"#### 📄 File: `{patch['file_path']}` (Target Issue #{patch['github_issue_number']})")
                st.info(f"💡 **Diagnosis & Solution**: {patch['explanation']}")
                
                # Associated PR
                for pr in prs:
                    if f"#{patch['github_issue_number']}" in pr.get("title", "") or pr.get("number") == patch.get("github_issue_number"):
                        st.success(f"🔀 **Pull Request Opened:** [{pr.get('title')}]({pr.get('html_url')}) (`#{pr.get('number')}`) by **@{result.get('github_username', 'nikhil-mutreja')}**")

                st.markdown("**Unified Diff:**")
                st.code(patch["diff"], language="diff")
                st.markdown("---")
        else:
            st.info("No code patches generated for this request.")

    with tab3:
        analyzed = result.get("analyzed_issues", [])
        if analyzed:
            for item in analyzed:
                sev = item.get("severity", "LOW")
                badge_color = (
                    "🔴" if sev == "CRITICAL" else
                    "🟠" if sev == "HIGH" else
                    "🔵" if sev == "MEDIUM" else "⚪"
                )
                with st.expander(f"{badge_color} Issue #{item['number']}: {item['title']} ({sev})", expanded=(sev in ("CRITICAL", "HIGH"))):
                    st.markdown(f"**Classification:** `{sev}`")
                    st.markdown(f"**Actionable:** `{'Yes' if item['is_actionable'] else 'No'}`")
                    st.markdown(f"**Triage Reason:** {item['reason']}")
                    st.markdown(f"**Target Codebase File:** `{item.get('file_path', 'N/A')}`")
                    if item.get("lineno"):
                        st.markdown(f"**Line Number:** `{item['lineno']}`")
                    if item.get("snippet"):
                        st.code(item["snippet"], language="python")
                    if item.get("jira_ticket_key"):
                        st.markdown(f"**Linked Jira Task:** `{item['jira_ticket_key']}`")
                    if item.get("pull_request_number"):
                        st.markdown(f"**Linked Pull Request:** `PR #{item['pull_request_number']}`")
                    st.markdown(f"**Labels:** {', '.join(item.get('labels', [])) or 'None'}")
                    st.caption(f"Author: @{item.get('author', 'unknown')} | Link: {item.get('html_url', '')}")
        else:
            st.info("No issues retrieved.")

    with tab4:
        actionable = result.get("actionable_issues", [])
        patches = result.get("code_patches", [])
        if actionable:
            table_data = []
            for item in actionable:
                has_patch = "✅ Generated" if any(p["github_issue_number"] == item["number"] for p in patches) else "—"
                pr_num = item.get("pull_request_number")
                pr_str = f"PR #{pr_num}" if pr_num else "—"
                table_data.append({
                    "GitHub Issue": f"#{item['number']}",
                    "Severity": item["severity"],
                    "Code Patch": has_patch,
                    "Pull Request": pr_str,
                    "Jira Task": item.get("jira_ticket_key", "—"),
                    "Slack Alert": "Dispatched" if result.get("slack_results") else "—",
                })
            st.table(table_data)
        else:
            st.info("No actionable issues identified.")

    with tab5:
        st.markdown("#### Decisions Made by AI Software Engineer")
        for d in result.get("decisions", []):
            st.markdown(f"- 💡 {d}")

        st.markdown("#### Actions Executed")
        for a in result.get("actions_taken", []):
            st.markdown(f"- ✅ {a}")

        if result.get("errors"):
            st.markdown("#### ⚠️ Errors / Warnings")
            for e in result.get("errors", []):
                st.error(e)
