"""DevPilot: Streamlit Interactive Demonstration Dashboard."""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
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
    st.subheader("Repository & Workspace")
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

# Demo Quick Prompts
st.markdown("#### ⚡ Autonomous Software Engineering Tasks")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🛠️ Fix Bug & Open PR", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Investigate and fix bug #102: payment gateway 500 error on checkout, "
            "open a pull request with the fix, create a Jira task, and notify Slack."
        )

with col2:
    if st.button("🔒 Security Remediation", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Remediate critical security vulnerability #101: token leakage in OAuth callback, "
            "generate code patch, open PR, track in Jira, and alert the team on Slack."
        )

with col3:
    if st.button("✨ Feature Development", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Implement dark mode theme switcher #105, commit the frontend changes, "
            "create a pull request, create a Jira ticket, and notify Slack."
        )

with col4:
    if st.button("📋 Repo Triage & Tracking", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Analyze latest GitHub repository issues, identify critical items, "
            "create Jira tasks, and notify the team on Slack."
        )

default_prompt = st.session_state.get(
    "user_prompt",
    "Investigate and fix bug #102: payment gateway 500 error on checkout, "
    "open a pull request with the fix, create a Jira task, and notify Slack.",
)

user_request = st.text_area(
    "Enter natural-language engineering task for DevPilot:",
    value=default_prompt,
    height=90,
)

run_button = st.button("🚀 Run AI Software Engineer", type="primary", use_container_width=True)

if run_button and user_request:
    with st.spinner("DevPilot AI Software Engineer executing end-to-end coding workflow..."):
        result = run_devpilot_agent(
            user_request=user_request,
            repo_owner=repo_owner,
            repo_name=repo_name,
            jira_project=jira_project,
            slack_channel=slack_channel,
            app_mode=app_mode,
        )

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
        f"**Task Type:** `{result.get('task_type')}` | **Swytchcode Tools Invoked:** `{', '.join(selected_tools) or 'None'}`"
    )

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Executive Summary",
        "💻 Code Patches & PRs",
        "🔍 Triaged Issues",
        "🔗 Traceability Matrix",
        "📜 Decisions & Audit Trail",
    ])

    with tab1:
        st.markdown(result.get("final_response", "Workflow completed."))

    with tab2:
        patches = result.get("code_patches", [])
        prs = result.get("pull_requests", [])
        if patches:
            for patch in patches:
                st.markdown(f"#### 📄 File: `{patch['file_path']}` (Target Issue #{patch['github_issue_number']})")
                st.info(f"💡 **Diagnosis & Solution**: {patch['explanation']}")
                
                # Associated PR
                for pr in prs:
                    if f"#{patch['github_issue_number']}" in pr.get("title", ""):
                        st.success(f"🔀 **Pull Request Opened:** [{pr.get('title')}]({pr.get('html_url')}) (`#{pr.get('number')}`)")

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
