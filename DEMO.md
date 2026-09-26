# DevPilot — Jury Demo Guide (2.5 Minutes)

This document provides a concise sequence for demonstrating **DevPilot** to the hackathon jury within the 2.5-minute presentation window.

---

## 2.5-Minute Demo Timeline

| Time | Stage | Action / Talking Point | What Judges See |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:30** | **The Problem & Concept** | Introduce DevPilot as an autonomous software engineering agent built with LangGraph and Swytchcode that bridges GitHub, Jira, and Slack. Emphasize that it is **not a rigid pipeline**, but a truly conditional agent. | Streamlit Dashboard header and Swytchcode integration badges (`github.issue.get1`, `jira.api.issue.create`, `slack.chat.postmessage.create`). |
| **0:30 - 1:00** | **Step 1: Conditional Triage** | Click **"1. GitHub Triage Only"** button. Explain that when only analysis is requested, the agent invokes GitHub and triages issues without calling Jira or Slack unnecessarily. | Metric counters update: Issues triaged (5), Actionable found (3), Jira (0), Slack (0). Show severity breakdown (`CRITICAL`, `HIGH`, `LOW`). |
| **1:00 - 1:45** | **Step 2: Primary Multi-Step Flow** | Click **"3. Full Multi-Step Flow"** ("Analyze critical GitHub issues, create Jira tasks, and notify Slack"). Run the agent. Explain how API output from GitHub triggers triage, actionable items trigger Jira tasks, and Jira keys are embedded into the Slack message. | Live progress counters update: Issues triaged (5), Actionable (3), Jira Tasks created (3), Slack notifications (1). |
| **1:45 - 2:15** | **Step 3: Traceability & Decisions** | Click the **"Traceability Matrix"** tab and **"Decisions & Audit Trail"** tab. Show how Issue #101 (`Remote token leak`) and Issue #102 (`Payment 500`) are mapped directly to `DEV-201` and `DEV-202` and dispatched to Slack. | Visual traceability table linking GitHub issue → Severity → Jira Ticket → Slack Alert. Decision log showing why each tool was selected. |
| **2:15 - 2:30** | **Conclusion & Q&A Transition** | Summarize: Real LangGraph agent, 3 Swytchcode APIs, conditional decision-making, dual Real/Mock mode, and 100% test coverage. Open for Q&A. | Clean final report in Executive Summary tab. |

---

## Demo Prompts

### Primary Demo Prompt (Full Workflow)
```text
Analyze the latest issues in my GitHub repository, identify the critical or actionable issues, create appropriate Jira tasks for those issues, and notify the relevant development team on Slack.
```

### Contrast Prompt (Conditional Skipping)
```text
Analyze my GitHub repository issues and assess severity.
```
*(Demonstrates that Jira and Slack are intentionally skipped when not requested).*

---

## What to Highlight to Judges

1. **Autonomous Tool Selection**: The agent inspects natural-language intent and only selects required Swytchcode tools.
2. **True Conditional Logic**: Contrast Prompt 1 (GitHub only) with Prompt 3 (Full pipeline) to prove the agent makes runtime decisions.
3. **Data Dependency**: The Slack alert actually contains the generated Jira ticket key and GitHub issue number—proving multi-step integration where step N depends on step N-1.
4. **Swytchcode Governance**: Point out `.swytchcode/tooling.json` containing `github.issue.get1`, `jira.api.issue.create`, and `slack.chat.postmessage.create`.
5. **Production Readiness**: Zero dead code, full test suite (`pytest`), and clean error handling.
