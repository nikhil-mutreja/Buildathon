# DevPilot — Jury Demo Guide (2.5 Minutes)
**Track 1: AI Software Engineer — Build with Swytchcode**

This guide provides a concise walkthrough to demonstrate DevPilot to the hackathon jury within the 2.5-minute window.

---

## 2.5-Minute Demo Timeline

| Time | Stage | Action / Talking Point | What Judges See |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:30** | **The Objective** | Introduce DevPilot as an autonomous **AI Software Engineer** built with LangGraph and Swytchcode. Explain that it does not merely triage issues, but actively **works with code repositories, writes patches, opens Pull Requests, tracks tasks in Jira, and communicates on Slack**. | Streamlit Dashboard header and registered Swytchcode tool capabilities (`github.content.get`, `github.pull.create`, `jira.api.issue.create`, `slack.chat.postmessage.create`). |
| **0:30 - 1:15** | **Autonomous Coding & PR** | Click **"🛠️ Fix Bug & Open PR"** ("Investigate and fix bug #102: payment gateway 500 error on checkout, open a pull request with the fix, create a Jira task, and notify Slack"). Run the agent. | Agent analyzes the task, inspects `src/services/payment_service.py` via `github.content.get`, diagnoses float precision error, generates Decimal patch, opens PR via `github.pull.create`, creates Jira task, and alerts Slack. |
| **1:15 - 1:50** | **Code Diff & Traceability** | Navigate to the **"💻 Code Patches & PRs"** tab and **"🔗 Traceability Matrix"** tab. Show the actual syntax-highlighted unified diff and the live PR link. | Unified diff showing exact code changes, clickable Pull Request `#53`, linked Jira task `DEV-202`, and Slack alert. |
| **1:50 - 2:15** | **Conditional Flexibility** | Click **"📋 Repo Triage & Tracking"** or **"✨ Feature Development"** to demonstrate that the agent adapts dynamically to the developer's instructions instead of following a rigid script. | Agent transitions between task types (`bug_fix`, `feature_development`, `issue_triage`), dynamically adjusting tool selection. |
| **2:15 - 2:30** | **Wrap Up & Q&A** | Highlight: 100% test coverage (`pytest`), zero hardcoded pipelines, full Swytchcode governance, and production-ready architecture. | Executive Summary tab and clean decision audit trail. |

---

## Demo Task Prompts

### 1. Primary Autonomous Coding Workflow (Bug Fix + PR)
```text
Investigate and fix bug #102: payment gateway 500 error on checkout, open a pull request with the fix, create a Jira task, and notify Slack.
```

### 2. Security Vulnerability Remediation
```text
Remediate critical security vulnerability #101: token leakage in OAuth callback, generate code patch, open PR, track in Jira, and alert the team on Slack.
```

### 3. Feature Development
```text
Implement dark mode theme switcher #105, commit the frontend changes, create a pull request, create a Jira ticket, and notify Slack.
```

---

## Key Points to Emphasize to Judges

1. **Complete Track 1 Alignment**: Automates coding workflows, repository code inspection, issue management, task tracking, and team communication.
2. **Real Code Artifacts**: Generates real unified diffs and Pull Requests, not just chat text.
3. **Swytchcode Governance**: Interacts with repository files (`github.content.get`), commits changes (`github.content.update`), creates PRs (`github.pull.create`), creates Jira tasks (`jira.api.issue.create`), and posts Slack messages (`slack.chat.postmessage.create`).
4. **End-to-End Traceability**: Seamlessly links `GitHub Issue #102` $\rightarrow$ `Code Patch` $\rightarrow$ `Pull Request #45` $\rightarrow$ `Jira DEV-202` $\rightarrow$ `Slack Alert`.
