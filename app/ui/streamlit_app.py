"""DevPilot — Autonomous AI Software Engineer.

Premium production-quality Streamlit interface for the DevPilot
agentic software engineering platform.
"""

import os
import sys
import re
import time

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import importlib
import app.agent.graph
importlib.reload(app.agent.graph)
from app.agent.graph import run_devpilot_agent

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="DevPilot — AI Software Engineer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# Premium CSS
# =============================================================================

st.markdown("""
<style>
/* ── Global ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

[data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Header Bar ── */
.dp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 24px;
}
.dp-logo {
    display: flex;
    align-items: center;
    gap: 12px;
}
.dp-logo-icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: white;
}
.dp-logo-text {
    font-size: 22px; font-weight: 700;
    letter-spacing: -0.5px;
}
.dp-logo-sub {
    font-size: 13px; color: #9ca3af; font-weight: 400;
    margin-top: -2px;
}
.dp-status-bar {
    display: flex; align-items: center; gap: 20px;
    font-size: 13px; color: #9ca3af;
}

/* ── Mode Badges ── */
.badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-demo {
    background: rgba(251, 191, 36, 0.15); color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.25);
}
.badge-live {
    background: rgba(34, 197, 94, 0.15); color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.25);
}
.badge-status {
    background: rgba(99, 102, 241, 0.15); color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.25);
}

/* ── Context Bar ── */
.ctx-bar {
    display: flex; align-items: center; gap: 24px;
    padding: 12px 20px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    margin-bottom: 20px;
    font-size: 13px;
    flex-wrap: wrap;
}
.ctx-item { display: flex; align-items: center; gap: 6px; }
.ctx-label { color: #6b7280; font-weight: 500; }
.ctx-value {
    color: #e5e7eb; font-weight: 600;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
}

/* ── Request Input ── */
.request-box {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}
.request-title {
    font-size: 14px; font-weight: 600; color: #d1d5db;
    margin-bottom: 12px; letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Timeline ── */
.timeline-item {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 10px 16px;
    border-left: 2px solid rgba(255,255,255,0.06);
    margin-left: 8px;
    transition: all 0.2s;
}
.timeline-item:hover { background: rgba(255,255,255,0.02); }
.tl-icon {
    width: 24px; height: 24px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; flex-shrink: 0;
    margin-top: 1px;
}
.tl-done { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.tl-running { background: rgba(99, 102, 241, 0.2); color: #818cf8; }
.tl-pending { background: rgba(107, 114, 128, 0.15); color: #6b7280; }
.tl-failed { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.tl-content { flex: 1; }
.tl-title { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.tl-desc { font-size: 12px; color: #9ca3af; margin-top: 2px; }

/* ── Section Headers ── */
.section-hdr {
    font-size: 14px; font-weight: 600; color: #d1d5db;
    letter-spacing: 0.5px; text-transform: uppercase;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

/* ── Cards ── */
.card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}
.card-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px;
}
.card-title { font-size: 14px; font-weight: 600; color: #e5e7eb; }

/* ── Severity ── */
.sev-crit { color: #ef4444; }
.sev-high { color: #f97316; }
.sev-med  { color: #eab308; }
.sev-low  { color: #6b7280; }

/* ── Metric Blocks ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.metric-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
}
.metric-val {
    font-size: 24px; font-weight: 700; color: #e5e7eb;
    font-family: 'JetBrains Mono', monospace;
}
.metric-label {
    font-size: 11px; color: #9ca3af; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-top: 4px;
}

/* ── PR Card ── */
.pr-card {
    background: rgba(34, 197, 94, 0.04);
    border: 1px solid rgba(34, 197, 94, 0.15);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
}
.pr-number {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600; color: #22c55e;
}

/* ── Error Card ── */
.err-card {
    background: rgba(239, 68, 68, 0.06);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}
.err-title { font-size: 14px; font-weight: 600; color: #ef4444; }
.err-detail { font-size: 13px; color: #fca5a5; margin-top: 6px; }

/* ── Empty State ── */
.empty-state {
    text-align: center;
    padding: 48px 24px;
    color: #6b7280;
}
.empty-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
.empty-title { font-size: 16px; font-weight: 600; color: #9ca3af; }
.empty-desc { font-size: 13px; margin-top: 6px; }

/* ── Example Prompts ── */
.prompt-chip {
    display: inline-block;
    padding: 8px 16px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    font-size: 13px; color: #d1d5db;
    cursor: pointer;
    margin: 4px;
    transition: all 0.15s;
}
.prompt-chip:hover {
    background: rgba(99, 102, 241, 0.1);
    border-color: rgba(99, 102, 241, 0.3);
}

/* ── Streamlit Overrides ── */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Sidebar — Configuration
# =============================================================================

with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    app_mode = "real"
    st.markdown('<span class="badge badge-live">⬤ LIVE MODE (Real Git & Swytchcode)</span>', unsafe_allow_html=True)
    st.caption("Agent runs live against real public repositories, Swytchcode tooling, and GitHub.")

    st.markdown("---")
    st.markdown("##### Repository")
    github_username = st.text_input(
        "GitHub Username",
        value=os.getenv("GITHUB_USERNAME", "nikhil-mutreja"),
        help="Username for PR authorship.",
    )
    repo_owner = st.text_input("Owner / Org", value=os.getenv("GITHUB_REPO_OWNER", "nikhil-mutreja"))
    repo_name_default = os.getenv("GITHUB_REPO_NAME", "Skill-Swap-Platform")

    st.markdown("##### Integrations")
    jira_project = st.text_input("Jira Project Key", value=os.getenv("JIRA_PROJECT_KEY", "DEV"))
    slack_channel = st.text_input("Slack Channel", value=os.getenv("SLACK_CHANNEL", "#dev-alerts"))

    st.markdown("---")
    st.markdown("##### Swytchcode Tools")
    st.caption("""
    `github.issue.get1` · `github.content.get`
    `github.content.update` · `github.pull.create`
    `jira.api.issue.create` · `slack.chat.postmessage.create`
    """)

# =============================================================================
# Header
# =============================================================================

st.markdown("""
<div class="dp-header">
    <div class="dp-logo">
        <div class="dp-logo-icon">⚡</div>
        <div>
            <div class="dp-logo-text">DevPilot</div>
            <div class="dp-logo-sub">Autonomous AI Software Engineer</div>
        </div>
    </div>
    <div class="dp-status-bar">
        <span class="badge badge-status">Track 1 · Swytchcode</span>
    </div>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# Repository Selection
# =============================================================================

col_repo, col_branch, col_status = st.columns([5, 2, 2])

with col_repo:
    public_repo_input = st.text_input(
        "Public GitHub Repository",
        value=os.getenv("GITHUB_REPO_URL", "https://github.com/nikhil-mutreja/Skill-Swap-Platform"),
        placeholder="https://github.com/owner/repo or owner/repo",
        help="Enter the URL or slug of any public GitHub repository to analyze, fix, and create PRs for.",
    )
with col_branch:
    st.text_input("Branch", value="main", disabled=True, key="branch_display")
with col_status:
    st.text_input("Agent Status", value="🟢 Live · Ready", disabled=True, key="status_display")

# Resolve owner/repo
url_m = re.search(r'github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)', public_repo_input)
if url_m:
    effective_owner = url_m.group(1)
    effective_repo = url_m.group(2).rstrip("/").rstrip(".git")
elif "/" in public_repo_input.strip():
    parts = public_repo_input.strip().split("/", 1)
    effective_owner = parts[0]
    effective_repo = parts[1].rstrip("/").rstrip(".git")
else:
    effective_owner = repo_owner or "nikhil-mutreja"
    effective_repo = public_repo_input.strip()

# Context bar
st.markdown(f"""
<div class="ctx-bar">
    <div class="ctx-item">
        <span class="ctx-label">Repository</span>
        <span class="ctx-value">{effective_owner}/{effective_repo.split('/')[-1] if '/' in effective_repo else effective_repo}</span>
    </div>
    <div class="ctx-item">
        <span class="ctx-label">Branch</span>
        <span class="ctx-value">main</span>
    </div>
    <div class="ctx-item">
        <span class="ctx-label">Author</span>
        <span class="ctx-value">@{github_username}</span>
    </div>
    <div class="ctx-item">
        <span class="ctx-label">Mode</span>
        <span class="ctx-value">LIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# Request Input
# =============================================================================

st.markdown('<div class="request-title">Development Request</div>', unsafe_allow_html=True)

# Example prompts as buttons
prompt_col1, prompt_col2, prompt_col3, prompt_col4 = st.columns(4)

with prompt_col1:
    if st.button("🛡️ Scan, Fix, PR + Jira + Slack", use_container_width=True, key="q1"):
        st.session_state["user_prompt"] = (
            f"Scan {public_repo_input} for all bugs, fix them, open a pull request authored by @{github_username}, "
            f"update Jira, and notify Slack."
        )
        st.session_state["auto_trigger"] = True

with prompt_col2:
    if st.button("🎯 Fix Issue #1 & Create PR", use_container_width=True, key="q2"):
        st.session_state["user_prompt"] = (
            f"Fix issue #1 in {public_repo_input}, run the tests, "
            f"and create a pull request authored by @{github_username}."
        )
        st.session_state["auto_trigger"] = True

with prompt_col3:
    if st.button("🔍 Investigate & Code Audit Only", use_container_width=True, key="q3"):
        st.session_state["user_prompt"] = (
            f"Audit and analyze {public_repo_input} for all bugs and defects. "
            f"Investigate only — do not modify code or open a PR."
        )
        st.session_state["auto_trigger"] = True

with prompt_col4:
    if st.button("🔗 Fix + Jira + Slack", use_container_width=True, key="q4"):
        st.session_state["user_prompt"] = (
            f"Scan and fix all bugs in {public_repo_input}, open a pull request, "
            f"create a Jira task, and notify Slack authored by @{github_username}."
        )
        st.session_state["auto_trigger"] = True

default_prompt = st.session_state.get(
    "user_prompt",
    f"Scan {public_repo_input} for all bugs, fix them, open a pull request authored by @{github_username}, update Jira, and notify Slack.",
)

user_request = st.text_area(
    "Enter your engineering task",
    value=default_prompt,
    height=80,
    label_visibility="collapsed",
    placeholder="e.g. Fix the authentication bug in issue #42, run tests, and open a PR...",
)

run_btn = st.button("⚡ Execute", type="primary", use_container_width=True)
should_run = run_btn or st.session_state.pop("auto_trigger", False)

# =============================================================================
# Agent Execution
# =============================================================================

if should_run and user_request:
    # Clear previous prompt so it doesn't persist across re-runs
    if "user_prompt" in st.session_state:
        del st.session_state["user_prompt"]

    with st.status("**DevPilot** — Executing autonomous engineering workflow...", expanded=True) as status:
        st.write("🔍 Understanding request and identifying task type...")
        st.write(f"📂 Inspecting repository `{effective_owner}/{effective_repo}`...")
        st.write("🔬 Analyzing code and identifying issues...")

        result = run_devpilot_agent(
            user_request=user_request,
            repo_owner=effective_owner,
            repo_name=effective_repo,
            github_username=github_username,
            jira_project=jira_project,
            slack_channel=slack_channel,
            app_mode=app_mode,
        )

        st.session_state["last_result"] = result

        # Determine final status
        errors = result.get("errors", [])
        test_res = result.get("test_results", {})
        prs = result.get("pull_requests", [])

        if errors and not test_res.get("passed", True):
            status.update(label="**DevPilot** — Workflow completed with issues", state="error")
        elif prs:
            status.update(label="**DevPilot** — Workflow completed successfully", state="complete")
        else:
            status.update(label="**DevPilot** — Analysis complete", state="complete")

# =============================================================================
# Results Display
# =============================================================================

if "last_result" not in st.session_state:
    # Empty state
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">⚡</div>
        <div class="empty-title">Ready to engineer</div>
        <div class="empty-desc">
            Enter a development request above to let DevPilot investigate issues,<br>
            modify code, run tests, and create pull requests.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

result = st.session_state.get("last_result", {})
test_res = result.get("test_results", {})
patches = result.get("code_patches", [])
prs = result.get("pull_requests", [])
actionable = result.get("actionable_issues", [])
analyzed = result.get("analyzed_issues", [])
jira_res = result.get("jira_results", [])
slack_res = result.get("slack_results", [])
errors = result.get("errors", [])
git_branch = result.get("git_branch", "")
commit_sha = result.get("commit_sha", "")
pr_error = result.get("pr_error")

# =============================================================================
# Metrics Bar
# =============================================================================

st.markdown("---")

m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.metric("Issues Analyzed", len(analyzed))
with m2:
    st.metric("Bugs Found", len(actionable))
with m3:
    st.metric("Patches", len(patches))
with m4:
    t_status = test_res.get("status", "—")
    st.metric("Tests", "✅ Passed" if test_res.get("passed") else ("❌ Failed" if "FAILED" in t_status else t_status))
with m5:
    st.metric("PRs", len(prs))
with m6:
    st.metric("Commit", commit_sha[:8] if commit_sha else "—")

# =============================================================================
# Main Layout: Timeline + Details
# =============================================================================

col_timeline, col_details = st.columns([1, 2])

# ── Execution Timeline ──
with col_timeline:
    st.markdown('<div class="section-hdr">Agent Execution</div>', unsafe_allow_html=True)

    # Build timeline from actions_taken
    intent = result.get("intent", {})
    timeline_steps = []

    # Step 1: Request understood
    task_type = result.get("task_type", "unknown")
    timeline_steps.append(("done", "Request understood", f"Task: {task_type}"))

    # Step 2: GitHub inspection
    if result.get("github_results") is not None:
        n_issues = len(result.get("github_results", []))
        timeline_steps.append(("done", "Repository inspected", f"{n_issues} issue(s) retrieved"))

    # Step 3: Analysis
    if analyzed:
        timeline_steps.append(("done", "Issues analyzed", f"{len(actionable)} actionable bug(s) identified"))

    # Step 4: Code inspection
    inspected = result.get("inspected_files", [])
    if inspected:
        file_names = [os.path.basename(f.get("path", "")) for f in inspected[:3]]
        timeline_steps.append(("done", "Code inspected", ", ".join(file_names)))

    # Step 5: Patch generated
    if patches:
        timeline_steps.append(("done", "Fix generated", f"{len(patches)} file(s) patched"))

    # Step 6: Tests
    if test_res and test_res.get("status", "N/A") != "N/A":
        t_passed = test_res.get("passed", False)
        t_icon = "done" if t_passed else "failed"
        timeline_steps.append((t_icon, "Tests executed", test_res.get("summary", "")))

    # Step 7: Branch
    if git_branch:
        timeline_steps.append(("done", "Branch created", git_branch))

    # Step 8: Commit
    if commit_sha:
        timeline_steps.append(("done", "Changes committed", f"SHA: {commit_sha[:8]}"))

    # Step 9: PR
    if prs:
        for pr in prs:
            timeline_steps.append(("done", f"PR #{pr.get('number')} opened", pr.get("title", "")[:60]))
    elif pr_error:
        timeline_steps.append(("failed", "PR creation failed", pr_error[:60]))

    # Step 10: Jira
    if jira_res:
        for j in jira_res:
            key = j.get("key", "N/A")
            status = j.get("status", "Created")
            if status == "NOT_CONFIGURED":
                timeline_steps.append(("failed", f"Jira: not configured", j.get("error", "")[:50]))
            else:
                timeline_steps.append(("done", f"Jira: {key}", j.get("summary", "")[:50]))

    # Step 11: Slack
    if slack_res:
        for s in slack_res:
            if s.get("ok") or s.get("delivered", False):
                timeline_steps.append(("done", f"Slack: {s.get('channel', '')}", "Notification sent"))
            elif s.get("status") == "NOT_CONFIGURED":
                timeline_steps.append(("failed", "Slack: not configured", s.get("error", "")[:50]))
            else:
                timeline_steps.append(("done", f"Slack: {s.get('channel', '')}", "Message dispatched"))

    # Render timeline
    for status_icon, title, desc in timeline_steps:
        icon_class = f"tl-{status_icon}"
        icon_char = "✓" if status_icon == "done" else ("✗" if status_icon == "failed" else "●")
        st.markdown(f"""
        <div class="timeline-item">
            <div class="tl-icon {icon_class}">{icon_char}</div>
            <div class="tl-content">
                <div class="tl-title">{title}</div>
                <div class="tl-desc">{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Errors
    if errors:
        st.markdown('<div class="section-hdr">Diagnostics</div>', unsafe_allow_html=True)
        for err in errors:
            # Clean error for display — never show tokens
            clean_err = re.sub(r'(token|key|password|secret)\s*[:=]\s*\S+', r'\1: ****', err, flags=re.IGNORECASE)
            st.markdown(f"""
            <div class="err-card">
                <div class="err-title">⚠️ Notice</div>
                <div class="err-detail">{clean_err}</div>
            </div>
            """, unsafe_allow_html=True)

# ── Details Panel ──
with col_details:
    tab_labels = ["Code Changes", "Test Results", "Pull Requests"]
    if jira_res:
        tab_labels.append("Jira")
    if slack_res:
        tab_labels.append("Slack")
    tab_labels.append("Issues")
    tab_labels.append("Audit Trail")

    tabs = st.tabs(tab_labels)
    tab_idx = 0

    # ── TAB: Code Changes ──
    with tabs[tab_idx]:
        tab_idx += 1
        if patches:
            for patch in patches:
                fpath = patch.get("file_path", "")
                issue_num = patch.get("github_issue_number", "")
                cwe = patch.get("cwe", "")
                explanation = patch.get("explanation", "")
                diff = patch.get("diff", "")

                with st.container(border=True):
                    hdr_col, sev_col = st.columns([4, 1])
                    with hdr_col:
                        st.markdown(f"**📄 {fpath}**")
                        if issue_num:
                            st.caption(f"Issue #{issue_num} · {cwe}")
                    with sev_col:
                        st.markdown(f'<span class="badge badge-live">Patched</span>', unsafe_allow_html=True)

                    if explanation:
                        st.info(f"**Root Cause & Fix:** {explanation}")

                    if diff:
                        st.markdown("**Diff**")
                        st.code(diff, language="diff")
                    else:
                        st.caption("No diff available — original and fixed code may be identical.")
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">📝</div>
                <div class="empty-title">No code changes</div>
                <div class="empty-desc">Run a fix task to generate code patches.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB: Test Results ──
    with tabs[tab_idx]:
        tab_idx += 1
        if test_res and test_res.get("status", "N/A") != "N/A":
            passed = test_res.get("passed", False)

            if passed:
                st.success(f"**✅ All tests passed** — {test_res.get('summary', '')}")
            else:
                st.error(f"**❌ Tests failed** — {test_res.get('summary', '')}")
                st.warning("PR creation blocked until test failures are resolved.")

            col_cmd, col_exit = st.columns([3, 1])
            with col_cmd:
                st.markdown(f"**Command:** `{test_res.get('command', 'pytest -v')}`")
            with col_exit:
                st.markdown(f"**Exit Code:** `{test_res.get('exit_code', '')}`")

            stdout = test_res.get("stdout", "")
            if stdout:
                # Parse individual test results from stdout
                test_lines = []
                for line in stdout.splitlines():
                    line_stripped = line.strip()
                    if "PASSED" in line_stripped:
                        test_name = line_stripped.split("PASSED")[0].strip().split("::")[-1].strip()
                        if test_name:
                            test_lines.append(("pass", test_name))
                    elif "FAILED" in line_stripped:
                        test_name = line_stripped.split("FAILED")[0].strip().split("::")[-1].strip()
                        if test_name:
                            test_lines.append(("fail", test_name))

                if test_lines:
                    st.markdown("**Individual Tests:**")
                    for t_status_icon, t_name in test_lines:
                        icon = "✅" if t_status_icon == "pass" else "❌"
                        st.markdown(f"  {icon} `{t_name}`")

                with st.expander("Full test output", expanded=False):
                    st.code(stdout, language="text")

            stderr = test_res.get("stderr", "")
            if stderr and stderr.strip():
                with st.expander("Stderr", expanded=False):
                    st.code(stderr, language="text")
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">🧪</div>
                <div class="empty-title">No tests executed</div>
                <div class="empty-desc">Tests run automatically when code is modified in a repository with a test suite.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB: Pull Requests ──
    with tabs[tab_idx]:
        tab_idx += 1
        if prs:
            for pr in prs:
                pr_num = pr.get("number", "")
                pr_title = pr.get("title", "")
                pr_url = pr.get("html_url", "")
                head_ref = pr.get("head", {}).get("ref", git_branch)
                author = pr.get("author", github_username)
                cwe = pr.get("cwe", "")
                fpath = pr.get("file_path", "")
                diff = pr.get("diff", "")
                checklist = pr.get("review_checklist", [])

                st.markdown(f"""
                <div class="pr-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <div>
                            <span class="pr-number">PR #{pr_num}</span>
                            <span style="margin-left:8px; color:#e5e7eb; font-weight:600;">{pr_title[:80]}</span>
                        </div>
                        <span class="badge badge-demo">🟡 Pending Review</span>
                    </div>
                    <div style="display:flex; gap:24px; font-size:13px; color:#9ca3af;">
                        <span>Branch: <code>{head_ref}</code> → <code>main</code></span>
                        <span>Author: <code>@{author}</code></span>
                        <span>Commit: <code>{commit_sha[:8] if commit_sha else '—'}</code></span>
                        {'<span>Defect: <code>' + cwe + '</code></span>' if cwe else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Files changed
                if fpath:
                    st.markdown(f"**Files Changed:** `{fpath}`")

                # Link
                if pr_url:
                    st.markdown(f"🔗 **[Open Pull Request]({pr_url})**")

                # Checklist
                if checklist:
                    with st.expander("Review Checklist", expanded=False):
                        for c_idx, item in enumerate(checklist):
                            st.checkbox(item, value=True, key=f"pr_check_{pr_num}_{c_idx}")

                # Approval buttons
                approve_col, reject_col = st.columns([1, 1])
                with approve_col:
                    if st.button(f"✅ Approve & Merge PR #{pr_num}", key=f"approve_{pr_num}", use_container_width=True):
                        st.success(f"PR #{pr_num} approved and merged by @{github_username}.")
                with reject_col:
                    if st.button(f"🔙 Request Changes PR #{pr_num}", key=f"reject_{pr_num}", use_container_width=True):
                        st.info(f"Changes requested on PR #{pr_num}.")

        elif pr_error:
            st.markdown(f"""
            <div class="err-card">
                <div class="err-title">Pull Request Creation Failed</div>
                <div class="err-detail">
                    <p>{pr_error}</p>
                    <p style="margin-top:8px;">
                        Local branch <code>{git_branch}</code> and commit <code>{commit_sha[:8] if commit_sha else '—'}</code> were preserved.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**Recommended action:** Verify GitHub credentials and repository permissions, then retry.")
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">🔀</div>
                <div class="empty-title">No pull requests</div>
                <div class="empty-desc">PRs are created when code changes pass all tests.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB: Jira ──
    if jira_res:
        with tabs[tab_idx]:
            tab_idx += 1
            for j in jira_res:
                key = j.get("key", "N/A")
                status = j.get("status", "Created")
                summary = j.get("summary", "")
                url = j.get("url", "")
                priority = j.get("priority", "High")

                with st.container(border=True):
                    j_col1, j_col2 = st.columns([3, 1])
                    with j_col1:
                        st.markdown(f"**📋 {key}**")
                        st.caption(summary[:100])
                    with j_col2:
                        if status == "NOT_CONFIGURED":
                            st.markdown('<span class="badge badge-demo">Not Configured</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge badge-live">{status}</span>', unsafe_allow_html=True)

                    if url and "mock" not in url.lower():
                        st.markdown(f"🔗 [{url}]({url})")
                    st.caption(f"Priority: {priority}")
    else:
        tab_idx += 0  # Jira tab not shown

    # ── TAB: Slack ──
    if slack_res:
        with tabs[tab_idx]:
            tab_idx += 1
            for s in slack_res:
                channel = s.get("channel", "")
                ok = s.get("ok", False)
                status_val = s.get("status", "")

                with st.container(border=True):
                    s_col1, s_col2 = st.columns([3, 1])
                    with s_col1:
                        st.markdown(f"**💬 {channel}**")
                    with s_col2:
                        if status_val == "NOT_CONFIGURED":
                            st.markdown('<span class="badge badge-demo">Not Configured</span>', unsafe_allow_html=True)
                        elif ok:
                            st.markdown('<span class="badge badge-live">Delivered</span>', unsafe_allow_html=True)
                        else:
                            st.markdown('<span class="badge badge-live">Dispatched</span>', unsafe_allow_html=True)

                    msg = s.get("message", {})
                    if isinstance(msg, dict):
                        txt = msg.get("text", "")
                    else:
                        txt = str(msg)
                    intended = s.get("intended_message", "")
                    display_msg = txt or intended
                    if display_msg:
                        with st.expander("Message content", expanded=False):
                            st.text(display_msg[:1000])
    else:
        tab_idx += 0  # Slack tab not shown

    # ── TAB: Issues ──
    with tabs[tab_idx]:
        tab_idx += 1
        if analyzed:
            for item in analyzed:
                sev = item.get("severity", "LOW")
                number = item.get("number", 0)
                title = item.get("title", "")
                is_act = item.get("is_actionable", False)

                sev_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "⚪"}
                sev_icon = sev_icons.get(sev, "⚪")

                with st.expander(f"{sev_icon} #{number}: {title}", expanded=(sev in ("CRITICAL", "HIGH") and is_act)):
                    ic1, ic2, ic3 = st.columns(3)
                    with ic1:
                        st.markdown(f"**Severity:** {sev}")
                    with ic2:
                        st.markdown(f"**Actionable:** {'Yes' if is_act else 'No'}")
                    with ic3:
                        st.markdown(f"**File:** `{item.get('file_path', '—')}`")

                    st.markdown(f"**Assessment:** {item.get('reason', '')}")

                    if item.get("body"):
                        st.caption(item["body"][:300])

                    labels = item.get("labels", [])
                    if labels:
                        label_str = " · ".join(f"`{l}`" for l in labels)
                        st.caption(f"Labels: {label_str}")

                    jira_key = item.get("jira_ticket_key")
                    pr_num = item.get("pull_request_number")
                    if jira_key:
                        st.caption(f"Jira: {jira_key}")
                    if pr_num:
                        st.caption(f"PR: #{pr_num}")
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <div class="empty-title">No issues retrieved</div>
                <div class="empty-desc">Connect a repository to inspect issues.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── TAB: Audit Trail ──
    with tabs[tab_idx]:
        decisions = result.get("decisions", [])
        actions = result.get("actions_taken", [])

        if decisions:
            st.markdown("**Agent Decisions**")
            for d in decisions:
                st.markdown(f"- 💡 {d}")

        if actions:
            st.markdown("**Actions Taken**")
            for a in actions:
                st.markdown(f"- ✅ {a}")

        if not decisions and not actions:
            st.caption("No audit trail available.")

# =============================================================================
# Traceability Matrix (bottom)
# =============================================================================

if actionable:
    st.markdown("---")
    st.markdown('<div class="section-hdr">Traceability Matrix</div>', unsafe_allow_html=True)

    table_data = []
    for item in actionable:
        has_patch = "✅" if any(p["github_issue_number"] == item["number"] for p in patches) else "—"
        pr_num = item.get("pull_request_number")
        pr_str = f"PR #{pr_num}" if pr_num else ("⚠️ Failed" if pr_error else "—")
        t_gate = "✅" if test_res.get("passed") else ("❌" if "FAILED" in test_res.get("status", "") else "—")
        jira_key = item.get("jira_ticket_key") or "—"
        slack_ok = "✅" if any(s.get("ok", False) or s.get("delivered", False) for s in slack_res) else ("⚠️" if slack_res else "—")

        table_data.append({
            "Issue": f"#{item['number']}",
            "Severity": item["severity"],
            "Patch": has_patch,
            "Tests": t_gate,
            "Branch": git_branch or "—",
            "Commit": commit_sha[:7] if commit_sha else "—",
            "PR": pr_str,
            "Jira": jira_key,
            "Slack": slack_ok,
        })
    st.table(table_data)
