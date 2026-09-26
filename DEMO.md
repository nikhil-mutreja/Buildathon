# DevPilot — Jury Demo Guide (2.5 Minutes)
**Track 1: AI Software Engineer — Build with Swytchcode**

---

## 2.5-Minute Demo Timeline

| Time | Action | What Judges See |
| :--- | :--- | :--- |
| **0:00 - 0:20** | **"This is DevPilot, an autonomous AI Software Engineer."** Explain: it analyzes real repositories, diagnoses bugs, writes code fixes, runs tests, creates branches, commits, and opens PRs — then tracks work in Jira and notifies on Slack. | Clean IDE-like workspace with repository selector, context bar showing repo/branch/author/mode, and "Ready" status. |
| **0:20 - 0:45** | Click **"🎯 Fix Issue #1 & Create PR"**. This runs on `real_test_repo` — a real Git repository with real code and real failing tests. | Agent execution status expands: "Understanding request..." → "Inspecting repository..." → "Analyzing code..." |
| **0:45 - 1:15** | Results appear. Show the **execution timeline** on the left — each step the agent took with real data. Point out: "Request understood", "Issue retrieved", "Code inspected", "Fix generated", "Tests executed — all passed", "Branch created", "Changes committed", "PR opened". | Left timeline with ✓ checkmarks. Right panel shows metrics: Issues Analyzed, Bugs Found, Patches, Tests ✅ Passed, PRs, Commit SHA. |
| **1:15 - 1:35** | Click **"Code Changes"** tab. Show the actual unified diff. Point out: "This is a real code change — not a canned response. The agent read the code, identified the edge case, and generated this fix." | Professional diff view showing the actual patch with root cause explanation. |
| **1:35 - 1:50** | Click **"Test Results"** tab. Show: "All 3 tests passed. The agent ran pytest on the repository before creating the branch." Then click **"Pull Requests"** tab — show PR number, branch name, commit SHA, and the approval buttons. | Individual test results with ✅ marks. PR card with real data and "Approve & Merge" button. |
| **1:50 - 2:10** | Switch repository to `ecommerce_service`. Click **"🛡️ Scan & Fix All Bugs"**. Show that the agent autonomously discovers CWE-681 (float precision), CWE-89 (SQL injection), CWE-775 (file descriptor leak) — different bugs in different files, each with its own patch and PR. | Multiple patches, multiple PRs, traceability matrix linking Issue → Patch → Test → Branch → Commit → PR. |
| **2:10 - 2:30** | Wrap up: **"Every action you saw was real — real Git operations, real test execution, real code analysis. The agent adapts its workflow based on the request. It's not a chatbot — it's an engineer."** | Full traceability matrix at bottom. Audit trail showing every agent decision. |

---

## Quick Demo Prompts

### Primary: Fix Bug + Full Workflow
```text
Fix issue #1 in test_repositories/real_test_repo, run the tests, and create a pull request authored by @nikhil-mutreja.
```

### Security Scan: Multiple Bugs
```text
Scan test_repositories/ecommerce_service for bugs and security vulnerabilities, fix them, run tests, and create pull requests authored by @nikhil-mutreja.
```

### Investigate Only (Read-Only)
```text
Analyze issue #1 in test_repositories/real_test_repo. Investigate only — do not modify code or open a PR.
```

### Full Stack: Fix + Jira + Slack
```text
Fix issue #1 in test_repositories/real_test_repo, create a PR, create a Jira task, and notify Slack authored by @nikhil-mutreja.
```

---

## Key Points for Judges

1. **Real Code Operations**: Reads real files, writes real patches, runs real `pytest`, creates real Git branches and commits with actual SHA hashes.
2. **Conditional Agent**: Different requests trigger different subsets of the workflow — investigate-only skips code changes; no Jira/Slack unless explicitly requested.
3. **Test Safety Gate**: Agent blocks PR creation if tests fail — never pushes broken code.
4. **Transparent Execution**: No fake data. If a GitHub API call fails, it reports the actual error. If tests fail, it shows the failure. If a PR can't be created remotely, it says so honestly.
5. **Swytchcode Integration**: Uses registered tools `github.issue.get1`, `github.content.get`, `github.content.update`, `github.pull.create`, `jira.api.issue.create`, `slack.chat.postmessage.create`.
6. **Professional UI**: IDE-like workspace with execution timeline, code diffs, test results, PR review cards, and full traceability matrix.
