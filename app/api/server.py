"""DevPilot FastAPI Backend — SSE-enabled execution server for the LangGraph agent."""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Any, Generator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Ensure workspace root is in path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from app.agent.graph import build_devpilot_graph
from app.agent.state import DevPilotState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DevPilot.API")

app = FastAPI(title="DevPilot API", description="Backend API for DevPilot AI Software Engineer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
    user_request: str
    repo_owner: str = "nikhil-mutreja"
    repo_name: str = "real_test_repo"
    github_username: str = "nikhil-mutreja"
    jira_project: str = "DEV"
    slack_channel: str = "#dev-alerts"
    app_mode: str = "real"


def _safe_json(obj: Any) -> str:
    """JSON-serialize state, converting non-serializable types to strings."""
    def default_handler(o: Any) -> Any:
        return str(o)
    return json.dumps(obj, default=default_handler)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "DevPilot"}


@app.get("/api/repositories")
async def list_repositories():
    repo_dir = Path(WORKSPACE_ROOT) / "test_repositories"
    if not repo_dir.exists():
        return {"repositories": []}
    repos = sorted([item.name for item in repo_dir.iterdir() if item.is_dir()])
    return {"repositories": repos}


def _generate_events(req: ExecuteRequest) -> Generator[dict[str, Any], None, None]:
    """Stream LangGraph execution as SSE events, one per node completion."""
    try:
        graph = build_devpilot_graph()

        initial_state: DevPilotState = {
            "user_request": req.user_request,
            "repo_owner": req.repo_owner,
            "repo_name": req.repo_name,
            "github_username": req.github_username,
            "jira_project": req.jira_project,
            "slack_channel": req.slack_channel,
            "app_mode": req.app_mode,
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

        final_state: dict[str, Any] = dict(initial_state)

        for event in graph.stream(initial_state):
            for node_name, node_state in event.items():
                logger.info(f"[SSE] Node completed: {node_name}")
                final_state.update(node_state)

                yield {
                    "event": "step",
                    "data": _safe_json({
                        "node": node_name,
                        "status": "completed",
                        "data": dict(node_state),
                    }),
                }

        yield {
            "event": "complete",
            "data": _safe_json(final_state),
        }

    except Exception as e:
        logger.error(f"[SSE] Execution failed: {e}")
        yield {
            "event": "error",
            "data": _safe_json({"message": str(e)}),
        }


@app.post("/api/execute")
async def execute_agent(req: ExecuteRequest):
    """Execute the DevPilot agent and stream results via SSE."""
    return EventSourceResponse(_generate_events(req))
