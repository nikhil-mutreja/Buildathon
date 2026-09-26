"""DevPilot: Streamlit Interactive Demonstration Dashboard."""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.agent.graph import run_devpilot_agent

st.set_page_config(
    page_title="DevPilot — Autonomous AI Software Engineering Agent",
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
    .step-box {
        background: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 10px 14px;
        margin: 6px 0;
        border-radius: 0 4px 4px 0;
        font-family: monospace;
    }
    .decision-box {
        background: #eef7ff;
        border-left: 4px solid #17a2b8;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 0 4px 4px 0;
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
    st.subheader("Swytchcode Integrations")
    st.markdown(
        """
        - **GitHub**: `github.issue.get1`
        - **Jira**: `jira.api.issue.create`
        - **Slack**: `slack.chat.postmessage.create`
        """
    )
    st.caption("Registered in `.swytchcode/tooling.json`")

# Header
st.markdown('<div class="main-title">DevPilot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Autonomous AI Software Engineering Agent — Track 1: Build with Swytchcode</div>',
    unsafe_allow_html=True,
)

# Demo Quick Prompts
st.markdown("#### ⚡ Quick Demo Prompts for Hackathon Judges")
col1, col2, col3 = st.columns(3)

prompt_input = ""
with col1:
    if st.button("1. GitHub Triage Only", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Analyze my GitHub issues, evaluate severity, and report actionable findings."
        )

with col2:
    if st.button("2. GitHub + Jira Creation", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Find critical GitHub issues and create appropriate Jira tasks for our engineering backlog."
        )

with col3:
    if st.button("3. Full Multi-Step Flow", use_container_width=True):
        st.session_state["user_prompt"] = (
            "Analyze critical GitHub issues, create Jira tasks, and notify the development team on Slack."
        )

default_prompt = st.session_state.get(
    "user_prompt",
    "Analyze the latest issues in my GitHub repository, identify the critical or actionable issues, "
    "create appropriate Jira tasks for those issues, and notify the relevant development team on Slack.",
)

user_request = st.text_area(
    "Enter natural-language instruction for DevPilot:",
    value=default_prompt,
    height=90,
)

run_button = st.button("🚀 Run Agent", type="primary", use_container_width=True)

if run_button and user_request:
    with st.spinner("DevPilot LangGraph Agent executing multi-step workflow..."):
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
    st.subheader("🔄 Agent Workflow Execution")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("Issues Triaged", len(result.get("analyzed_issues", [])))
    with col_b:
        st.metric("Actionable Found", len(result.get("actionable_issues", [])))
    with col_c:
        st.metric("Jira Tasks Created", len(result.get("jira_results", [])))
    with col_d:
        st.metric("Slack Alerts Sent", len(result.get("slack_results", [])))

    # Selected Tools & Intent
    intent = result.get("intent", {})
    selected_tools = result.get("selected_tools", [])
    st.markdown(
        f"**Tools Selected by Agent:** `{', '.join(selected_tools) or 'None'}`"
    )

    # Decisions & Actions Taken
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Executive Summary", "🔍 Triaged Issues", "🔗 Traceability Matrix", "📜 Decisions & Audit Trail"])

    with tab1:
        st.markdown(result.get("final_response", "Workflow completed."))

    with tab2:
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
                    if item.get("jira_ticket_key"):
                        st.markdown(f"**Linked Jira Task:** `{item['jira_ticket_key']}`")
                    st.markdown(f"**Labels:** {', '.join(item.get('labels', [])) or 'None'}")
                    st.caption(f"Author: @{item.get('author', 'unknown')} | Link: {item.get('html_url', '')}")
        else:
            st.info("No issues retrieved.")

    with tab3:
        actionable = result.get("actionable_issues", [])
        if actionable:
            table_data = []
            for item in actionable:
                table_data.append({
                    "GitHub Issue": f"#{item['number']}",
                    "Title": item["title"],
                    "Severity": item["severity"],
                    "Jira Task": item.get("jira_ticket_key", "Skipped / None"),
                    "Slack Alert": "Dispatched" if result.get("slack_results") else "Skipped / None",
                })
            st.table(table_data)
        else:
            st.info("No actionable issues identified.")

    with tab4:
        st.markdown("#### Decisions Made by Agent")
        for d in result.get("decisions", []):
            st.markdown(f"- 💡 {d}")

        st.markdown("#### Actions Executed")
        for a in result.get("actions_taken", []):
            st.markdown(f"- ✅ {a}")

        if result.get("errors"):
            st.markdown("#### ⚠️ Errors / Warnings")
            for e in result.get("errors", []):
                st.error(e)
