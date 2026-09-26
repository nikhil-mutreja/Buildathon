"""Swytchcode Client: Unified execution layer adapter for GitHub, Jira, and Slack.

Supports both Live Swytchcode execution and high-fidelity Demo/Mock simulation.
Uses exact canonical tool IDs registered in Swytchcode:
- github.issue.get1
- github.content.get
- github.content.update
- github.pull.create
- jira.api.issue.create
- slack.chat.postmessage.create
"""

import os
import sys
import json
import time
import base64
import hashlib
import logging
import subprocess
from typing import Any, Optional

logger = logging.getLogger("DevPilot.Swytchcode")

# Canonical tool IDs as registered in Swytchcode tooling.json
TOOL_GITHUB_ISSUES = "github.issue.get1"
TOOL_GITHUB_CONTENT_GET = "github.content.get"
TOOL_GITHUB_CONTENT_UPDATE = "github.content.update"
TOOL_GITHUB_PULL_CREATE = "github.pull.create"
TOOL_JIRA_CREATE_ISSUE = "jira.api.issue.create"
TOOL_SLACK_POST_MESSAGE = "slack.chat.postmessage.create"


class SwytchcodeClient:
    """Interface to Swytchcode Execution Authority for agent tools."""

    def __init__(self, mode: Optional[str] = None):
        """Initialize client with mode ('real' or 'mock').

        Defaults to environment variable APP_MODE, falling back to 'mock' if
        credentials are not configured.
        """
        env_mode = os.getenv("APP_MODE", "").lower()
        if mode:
            self.mode = mode.lower()
        elif env_mode in ("real", "production"):
            self.mode = "real"
        else:
            self.mode = "mock"

        # Configure Swytchcode native binary execution environment
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        swy_bin = os.path.join(workspace_root, "node_modules/swytchcode-cli-linux-x64/bin/swytchcode")
        if os.path.isfile(swy_bin):
            os.environ["SWYTCHCODE_BIN"] = swy_bin
         # Avoid read-only home in sandbox

        self._swx = None
        if self.mode == "real":
            try:
                from swytchcode_runtime import Swytchcode
                self._swx = Swytchcode()
            except ImportError:
                logger.error("swytchcode_runtime not found in REAL mode.")
                raise RuntimeError("swytchcode_runtime is required for REAL mode execution.")

    def is_mock(self) -> bool:
        """Return True if running in Mock/Demo mode."""
        return self.mode == "mock"

    # =========================================================================
    # GitHub Repository Tools
    # =========================================================================

    def fetch_github_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch repository issues using real repository issue files or Swytchcode github.issue.get1."""
        # 1. Check if repository on disk provides real issue definitions
        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir:
            issues_dir = os.path.join(repo_dir, "issues")
            if os.path.isdir(issues_dir):
                disk_issues = []
                for fname in sorted(os.listdir(issues_dir)):
                    if fname.endswith(".json"):
                        fpath = os.path.join(issues_dir, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as jf:
                                idata = json.load(jf)
                                disk_issues.append(idata)
                        except Exception as e:
                            logger.warning(f"Error loading issue file {fpath}: {e}")
                if disk_issues:
                    logger.info(f"[TOOL] Found {len(disk_issues)} real issue(s) on disk in {issues_dir}")
                    return disk_issues
            # If repo on disk has no issues dir, return [] so autonomous code scan inspects real code
            if "test_repositories" in repo_dir or os.path.isdir(os.path.join(repo_dir, "src")):
                return []

        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating GitHub issues for {owner}/{repo}")
            return self._mock_github_issues(owner, repo)

        # 2. Execute Swytchcode live GitHub issue retrieval
        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_ISSUES} for {owner}/{repo}")
        args: dict[str, Any] = {
            "params": {
                "owner": owner,
                "repo": repo,
                "state": state,
                "per_page": per_page,
            }
        }

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_ISSUES, args)
            if isinstance(result, list):
                logger.info(f"[TOOL] GitHub returned {len(result)} issues via Swytchcode")
                return result
            elif isinstance(result, dict) and "items" in result:
                return result["items"]
            elif isinstance(result, dict) and "error" in result:
                raise RuntimeError(result.get("error", "Unknown Swytchcode error"))
            return [result] if result else []
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub error: {err_msg}")

    def _find_repository_directory(self, owner: str, repo: str) -> Optional[str]:
        """Resolve repository to an actual directory on disk if available."""
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        clean_repo = repo.rstrip("/")
        if clean_repo.endswith(".git"):
            clean_repo = clean_repo[:-4]
        repo_base = os.path.basename(clean_repo)

        candidates = [
            clean_repo,  # Direct path if passed by user
            os.path.join(workspace_root, clean_repo),
            os.path.join(workspace_root, "test_repositories", repo_base),
            os.path.join(workspace_root, "test_repositories", repo_base.replace("-", "_")),
            os.path.join(workspace_root, "test_repositories", clean_repo),
            f"/tmp/devpilot_repos/{owner}_{repo_base}",
            f"/tmp/devpilot_repos/{repo_base}",
            os.path.join(os.path.expanduser("~"), clean_repo),
        ]

        if repo_base in ["real_test_repo", "real-test-repo"]:
            candidates.insert(0, os.path.join(workspace_root, "test_repositories", "real_test_repo"))
        elif repo_base in ["ecommerce", "ecommerce-service", "ecommerce_service"]:
            candidates.insert(0, os.path.join(workspace_root, "test_repositories", "ecommerce_service"))
        elif repo_base in ["auth", "auth-microservice", "auth_microservice"]:
            candidates.insert(0, os.path.join(workspace_root, "test_repositories", "auth_microservice"))
        elif repo_base in ["realtime", "realtime-stream-service", "realtime_stream_service"]:
            candidates.insert(0, os.path.join(workspace_root, "test_repositories", "realtime_stream_service"))
        elif repo_base in ["buildathon"]:
            candidates.insert(0, workspace_root)

        for cand in candidates:
            if cand and os.path.isdir(cand):
                return os.path.abspath(cand)
        return None

    def get_repository_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> dict[str, Any]:
        """Fetch file contents from repository using real disk or Swytchcode github.content.get."""
        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir:
            full_path = os.path.join(repo_dir, path)
            if os.path.isfile(full_path):
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Compute git-style blob SHA (same algorithm git uses)
                raw = content.encode("utf-8")
                blob_header = f"blob {len(raw)}\0".encode()
                sha = hashlib.sha1(blob_header + raw).hexdigest()
                return {
                    "name": os.path.basename(path),
                    "path": path,
                    "sha": sha,
                    "size": len(raw),
                    "type": "file",
                    "raw_text": content,
                    "content": base64.b64encode(raw).decode("utf-8"),
                }

        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating repository file read for {path}")
            return self._mock_repository_file(path)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_CONTENT_GET} for {path}")
        args: dict[str, Any] = {
            "params": {
                "owner": owner,
                "repo": repo,
                "path": path,
                "ref": ref,
            }
        }

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_CONTENT_GET, args)
            data = result.get("data", result) if isinstance(result, dict) else result
            if isinstance(data, dict):
                content_b64 = data.get("content", "")
                raw_text = ""
                if content_b64:
                    try:
                        raw_text = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
                    except Exception:
                        raw_text = str(content_b64)
                return {
                    "name": data.get("name", os.path.basename(path)),
                    "path": data.get("path", path),
                    "sha": data.get("sha", ""),
                    "size": data.get("size", len(raw_text)),
                    "type": data.get("type", "file"),
                    "raw_text": raw_text,
                    "content": content_b64,
                    "_raw_result": result,
                }
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub content get failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub file read error: {err_msg}")

    def list_repository_files(
        self,
        owner: str,
        repo: str,
        ref: str = "main",
    ) -> list[str]:
        """List source code files in repository for inspection and defect scanning.

        Priority:
        1. Local disk scan (for repos with a local checkout).
        2. GitHub API tree listing (authenticated, rate-limit-aware) — real mode only.
        3. Mock file list — mock mode only.

        In REAL mode, never falls back to fixture data. Failures surface as RuntimeError.
        """
        # 1. Scan local disk if a checked-out repo is available
        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir and os.path.isdir(repo_dir):
            discovered = []
            for root, dirs, filenames in os.walk(repo_dir):
                dirs[:] = [d for d in dirs if d not in [".venv", ".git", "node_modules", "__pycache__", ".pytest_cache", ".swytchcode"]]
                for f in filenames:
                    if any(f.endswith(ext) for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]):
                        rel = os.path.relpath(os.path.join(root, f), repo_dir)
                        discovered.append(rel)
            if discovered:
                return sorted(discovered)

        # 2. Mock mode: return deterministic fixture list
        if self.is_mock():
            return [
                "src/services/payment_service.py",
                "src/auth/oauth_handler.py",
                "src/realtime/broker.py",
                "src/utils/file_manager.py",
                "src/database/query_builder.py",
                "src/api/user_service.py",
                "src/components/ThemeToggle.tsx",
            ]

        # 3. Real mode: authenticated GitHub API tree listing with rate-limit handling.
        # There is no Swytchcode tool for recursive tree listing (github.content.get
        # requires a known path and cannot list the root). We use the GitHub REST API
        # directly here, authenticated via GITHUB_TOKEN if available.
        # Swytchcode's stored OAuth credentials are not accessible from the Python
        # subprocess in all environments — the token env var is the authenticated path.
        import urllib.request as _urllib_req
        import urllib.error as _urllib_err
        import time as _time

        CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
        MAX_RETRIES = 3
        token = os.getenv("GITHUB_TOKEN")
        target_ref = ref if ref and ref not in ("main", "master") else "HEAD"
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{target_ref}?recursive=1"

        for attempt in range(MAX_RETRIES):
            req = _urllib_req.Request(url)
            req.add_header("User-Agent", "DevPilot-Agent/1.0")
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            if token:
                req.add_header("Authorization", f"Bearer {token}")

            try:
                with _urllib_req.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    tree = data.get("tree", [])
                    code_files = [
                        item["path"] for item in tree
                        if item.get("type") == "blob"
                        and any(item["path"].endswith(ext) for ext in CODE_EXTENSIONS)
                    ]
                    logger.info(f"[TOOL] GitHub tree listed {len(code_files)} code file(s) for {owner}/{repo}@{ref}")
                    return sorted(code_files)

            except _urllib_err.HTTPError as http_err:
                status = http_err.code
                # Read rate-limit headers from the error response
                remaining = http_err.headers.get("x-ratelimit-remaining", "?")
                reset_ts = http_err.headers.get("x-ratelimit-reset", "")
                retry_after = http_err.headers.get("retry-after", "")

                if status == 403 or status == 429:
                    # Rate limited — determine wait time
                    if retry_after:
                        wait_secs = int(retry_after)
                    elif reset_ts:
                        wait_secs = max(0, int(reset_ts) - int(_time.time())) + 1
                    else:
                        wait_secs = 2 ** attempt  # exponential backoff

                    human_reset = ""
                    if reset_ts:
                        import datetime
                        try:
                            human_reset = datetime.datetime.utcfromtimestamp(int(reset_ts)).strftime("%H:%M:%S UTC")
                        except Exception:
                            human_reset = reset_ts

                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            f"[TOOL] GitHub rate limit hit for {owner}/{repo} "
                            f"(remaining={remaining}, resets={human_reset}). "
                            f"Waiting {wait_secs}s before retry {attempt + 1}/{MAX_RETRIES - 1}."
                        )
                        _time.sleep(min(wait_secs, 60))  # cap wait at 60s per attempt
                        continue
                    else:
                        raise RuntimeError(
                            f"GitHub API rate limit exceeded for {owner}/{repo}. "
                            f"Remaining requests: {remaining}. "
                            f"Rate limit resets at: {human_reset or 'unknown'}. "
                            f"{'Authenticate with GITHUB_TOKEN for higher limits.' if not token else 'Wait until the reset window and retry.'}"
                        )

                elif status == 404:
                    raise RuntimeError(
                        f"Repository '{owner}/{repo}' not found or not accessible on GitHub "
                        f"(HTTP 404). Check the owner and repository name."
                    )
                elif status == 401:
                    raise RuntimeError(
                        f"GitHub authentication failed (HTTP 401) for '{owner}/{repo}'. "
                        f"Check that GITHUB_TOKEN is valid and has repo read access."
                    )
                elif status == 403 and remaining != "0":
                    raise RuntimeError(
                        f"GitHub access forbidden (HTTP 403) for '{owner}/{repo}'. "
                        f"The token may lack required permissions."
                    )
                else:
                    raise RuntimeError(
                        f"GitHub API error {status} listing files for '{owner}/{repo}': {http_err.reason}"
                    )

            except Exception as e:
                err_msg = str(e)
                if attempt < MAX_RETRIES - 1 and "timeout" in err_msg.lower():
                    backoff = 2 ** attempt
                    logger.warning(f"[TOOL] GitHub tree request timed out ({err_msg}). Retrying in {backoff}s.")
                    _time.sleep(backoff)
                    continue
                logger.error(f"[TOOL] Could not list files for {owner}/{repo}: {err_msg}")
                raise RuntimeError(f"Could not list repository files for {owner}/{repo}: {err_msg}")

        # Should not reach here
        raise RuntimeError(f"GitHub file listing failed for {owner}/{repo} after {MAX_RETRIES} attempts.")

    def update_repository_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> dict[str, Any]:
        # If repository exists on disk, apply real code modification directly
        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir:
            full_path = os.path.join(repo_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[TOOL] Real code file updated on disk: {full_path}")
            # Compute real git blob SHA for the written content
            raw = content.encode("utf-8")
            blob_header = f"blob {len(raw)}\0".encode()
            content_sha = hashlib.sha1(blob_header + raw).hexdigest()
            if self.is_mock():
                return {
                    "content": {"path": path, "sha": "mock-sha-commit-9921"},
                    "commit": {"message": message, "sha": "mock-commit-sha-4921"},
                }
            return {
                "content": {"path": path, "sha": content_sha},
                "commit": {"message": message, "sha": "pending-git-commit"},
            }

        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating repository file commit to branch {branch} for {path}")
            return {
                "content": {"path": path, "sha": "mock-sha-commit-9921"},
                "commit": {"message": message, "sha": "mock-commit-sha-4921"},
            }

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_CONTENT_UPDATE} on {path}")
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        body: dict[str, Any] = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if not sha:
            try:
                existing_file = self.get_repository_file(owner=owner, repo=repo, path=path, ref=branch)
                if isinstance(existing_file, dict) and existing_file.get("sha"):
                    sha = existing_file["sha"]
            except Exception:
                try:
                    existing_file = self.get_repository_file(owner=owner, repo=repo, path=path, ref="main")
                    if isinstance(existing_file, dict) and existing_file.get("sha"):
                        sha = existing_file["sha"]
                except Exception:
                    pass

        if sha:
            body["sha"] = sha
        args: dict[str, Any] = {
            "params": {"owner": owner, "repo": repo, "path": path},
            "body": body,
        }

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_CONTENT_UPDATE, args)
            if isinstance(result, dict):
                inner_data = result.get("data", {})
                status_code = result.get("status_code")
                data_status = inner_data.get("status") if isinstance(inner_data, dict) else None
                if status_code in (400, 404, 409, 422) or data_status in (400, 404, 409, 422, "400", "404", "409", "422") or "error" in result:
                    err_msg = inner_data.get("message") or result.get("error") or str(result)
                    raise RuntimeError(f"Swytchcode GitHub file update error: {err_msg}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub file update failed: {err_msg}")
            raise RuntimeError(f"Swytchcode GitHub file update error: {err_msg}")

    def create_git_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> dict[str, Any]:
        """Create a git branch via local git or Swytchcode github.git.refs.create.

        For local repos with a .git directory: uses git checkout -B.
        For remote-only GitHub repos: resolves base branch HEAD SHA via
        github.content.get, then calls github.git.refs.create with the real SHA.
        """
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating branch creation '{branch_name}' from '{base_branch}'")
            return {"branch": branch_name, "base": base_branch, "created": True, "mode": "mock"}

        # Local git repository: create branch on disk
        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir and os.path.isdir(os.path.join(repo_dir, ".git")):
            try:
                subprocess.run(["git", "config", "user.name", "DevPilot Agent"], cwd=repo_dir, check=False)
                subprocess.run(["git", "config", "user.email", "devpilot@agentic.ai"], cwd=repo_dir, check=False)
                subprocess.run(["git", "checkout", "-B", branch_name], cwd=repo_dir, check=True, capture_output=True, text=True)
                current = subprocess.run(["git", "branch", "--show-current"], cwd=repo_dir, capture_output=True, text=True).stdout.strip()
                logger.info(f"[TOOL] Real Git branch '{current}' checked out in {repo_dir}")
                return {"branch": current, "base": base_branch, "created": True, "directory": repo_dir}
            except Exception as e:
                err_msg = f"Failed to create git branch '{branch_name}': {e}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

        # Remote-only GitHub repo: resolve base branch HEAD SHA, then create ref via Swytchcode
        logger.info(f"[TOOL] Resolving HEAD SHA for {owner}/{repo}@{base_branch} via github.content.get")
        try:
            # Get any file to obtain the commit SHA. README.md is a common entry point.
            # We try several common filenames.
            sha = None
            for probe_path in ["README.md", "README", "readme.md", "src", "package.json", "setup.py"]:
                try:
                    content_result = self._swx.tools.execute(
                        TOOL_GITHUB_CONTENT_GET,
                        {"params": {"owner": owner, "repo": repo, "path": probe_path, "ref": base_branch}},
                    )
                    data = content_result.get("data", content_result)
                    if isinstance(data, dict):
                        sha = data.get("sha")
                    elif isinstance(data, list) and data:
                        sha = data[0].get("sha")
                    if sha:
                        # github.content.get returns blob/tree SHA, not commit SHA.
                        # We need the commit SHA from the response links or commit field.
                        # The data from Swytchcode wraps GitHub's content response which
                        # contains the blob SHA, not the commit SHA.
                        # For refs.create we need the latest commit SHA on the base branch.
                        # Use the git tree API via authenticated urllib to get commit SHA.
                        sha = self._get_branch_head_sha(owner, repo, base_branch)
                        if sha:
                            break
                except Exception:
                    continue

            if not sha:
                raise RuntimeError(
                    f"Could not resolve HEAD commit SHA for '{owner}/{repo}@{base_branch}'. "
                    f"Cannot create remote branch '{branch_name}'."
                )

            logger.info(f"[TOOL] Executing Swytchcode github.git.refs.create for branch '{branch_name}' at SHA {sha[:8]}...")
            result = self._swx.tools.execute(
                "github.git.refs.create",
                {
                    "params": {"owner": owner, "repo": repo},
                    "body": {
                        "ref": f"refs/heads/{branch_name}",
                        "sha": sha,
                    },
                },
            )
            if isinstance(result, dict):
                inner = result.get("data", {})
                status_code = result.get("status_code")
                data_status = inner.get("status") if isinstance(inner, dict) else None
                if status_code in (422, 400) or data_status in (422, 400, "422", "400") or "already exists" in str(result).lower():
                    if "already exists" in str(result).lower():
                        logger.info(f"[TOOL] Remote branch '{branch_name}' already exists on {owner}/{repo}. Reusing branch.")
                        return {"branch": branch_name, "base": base_branch, "created": True, "sha": sha or "HEAD"}
                    raise RuntimeError(f"Swytchcode branch creation error for '{owner}/{repo}@{branch_name}': {inner.get('message', str(result))}")

            logger.info(f"[TOOL] Remote branch '{branch_name}' created on {owner}/{repo}")
            return {"branch": branch_name, "base": base_branch, "created": True, "sha": sha, "result": result}

        except RuntimeError:
            raise
        except Exception as e:
            if "already exists" in str(e).lower() or "reference already exists" in str(e).lower():
                logger.info(f"[TOOL] Remote branch '{branch_name}' already exists on {owner}/{repo}. Reusing branch.")
                return {"branch": branch_name, "base": base_branch, "created": True, "sha": sha or "HEAD"}
            raise RuntimeError(f"Swytchcode branch creation error for '{owner}/{repo}@{branch_name}': {e}")

    def _get_branch_head_sha(self, owner: str, repo: str, branch: str) -> Optional[str]:
        """Get the HEAD commit SHA for a branch using authenticated GitHub API."""
        import urllib.request as _req
        import urllib.error as _uerr

        token = os.getenv("GITHUB_TOKEN")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}?per_page=1"
        req = _req.Request(url)
        req.add_header("User-Agent", "DevPilot-Agent/1.0")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with _req.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and data:
                    return data[0].get("sha")
                elif isinstance(data, dict):
                    return data.get("sha")
        except Exception as e:
            logger.warning(f"[TOOL] Could not get HEAD SHA for {owner}/{repo}@{branch}: {e}")
        return None


    def commit_changes(
        self,
        owner: str,
        repo: str,
        file_path: str,
        message: str,
        branch_name: str,
        content: str = "",
        sha: Optional[str] = None,
    ) -> dict[str, Any]:
        """Commit modified files to real Git repository or via Swytchcode."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating commit to branch '{branch_name}': {message}")
            return {
                "commit_sha": "mock-commit-sha-4921",
                "branch": branch_name,
                "message": message,
                "mode": "mock",
            }

        repo_dir = self._find_repository_directory(owner, repo)
        if repo_dir and os.path.isdir(os.path.join(repo_dir, ".git")):
            try:
                subprocess.run(["git", "config", "user.name", "DevPilot Agent"], cwd=repo_dir, check=False)
                subprocess.run(["git", "config", "user.email", "devpilot@agentic.ai"], cwd=repo_dir, check=False)
                subprocess.run(["git", "add", file_path], cwd=repo_dir, check=True, capture_output=True, text=True)
                subprocess.run(["git", "commit", "-m", message], cwd=repo_dir, capture_output=True, text=True)
                sha_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
                actual_sha = sha_res.stdout.strip()
                logger.info(f"[TOOL] Real Git commit created: SHA={actual_sha} on branch '{branch_name}'")
                return {
                    "commit_sha": actual_sha,
                    "branch": branch_name,
                    "message": message,
                    "file_path": file_path,
                    "directory": repo_dir,
                }
            except Exception as e:
                err_msg = f"Failed to commit changes to git: {e}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

        # For remote repositories without local git checkout: commit to branch via Swytchcode
        logger.info(f"[TOOL] Committing `{file_path}` to remote branch `{branch_name}` on {owner}/{repo}")
        return self.update_repository_file(
            owner=owner,
            repo=repo,
            path=file_path,
            content=content,
            message=message,
            branch=branch_name,
            sha=sha,
        )


    def run_tests(
        self,
        owner: str,
        repo: str,
        test_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run project tests via pytest and capture actual stdout/stderr and exit code.

        In mock mode: returns simulated successful test results.
        In real mode: executes real pytest; returns passed=False if tests fail or cannot run.
        """
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating test execution for {owner}/{repo}: all tests passed")
            return {
                "status": "TEST PASSED",
                "passed": True,
                "summary": "Mock test run completed: 3 passed in 0.05s",
                "stdout": "================ 3 passed in 0.05s ================",
                "stderr": "",
                "exit_code": 0,
                "command": "pytest tests/ -v",
            }

        repo_dir = self._find_repository_directory(owner, repo)
        if not repo_dir:
            return {
                "status": "NOT_AVAILABLE",
                "passed": False,
                "summary": "Remote-only repository without local test runner. Tests not executed.",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        test_dir = os.path.join(repo_dir, "tests")
        target = test_path if test_path and os.path.exists(os.path.join(repo_dir, test_path)) else (test_dir if os.path.isdir(test_dir) else None)

        if not target:
            return {
                "status": "NOT_AVAILABLE",
                "passed": False,
                "summary": "No test directory or test files detected in repository. Tests not executed.",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }


        abs_target = os.path.join(repo_dir, target) if not os.path.isabs(target) else target
        env = {**os.environ, "PYTHONPATH": repo_dir}

        try:
            res = subprocess.run(
                [sys.executable, "-m", "pytest", abs_target, "-v"],
                cwd=repo_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = res.returncode == 0
            status = "TEST PASSED" if passed else "TEST FAILED"
            summary_line = ""
            for line in reversed(res.stdout.splitlines()):
                if "passed" in line or "failed" in line or "error" in line:
                    summary_line = line.strip(" =")
                    break

            rel_target = os.path.relpath(abs_target, repo_dir)
            test_cmd = f"pytest {rel_target} -v"
            logger.info(f"[TOOL] Tests executed in {repo_dir}: Status={status} ({summary_line})")
            return {
                "status": status,
                "passed": passed,
                "summary": summary_line or ("Tests passed" if passed else "Tests failed"),
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "target": abs_target,
                "command": test_cmd,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "TEST FAILED",
                "passed": False,
                "summary": "Test execution timed out after 30 seconds.",
                "stdout": "",
                "stderr": "TimeoutExpired",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "status": "TEST COULD NOT RUN",
                "passed": False,
                "summary": f"Could not execute test runner: {str(e)}",
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        author: str = "nikhil-mutreja",
    ) -> dict[str, Any]:
        """Create a pull request in repository using Swytchcode github.pull.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Pull Request creation by @{author}: {title} ({head} -> {base})")
            return self._mock_pull_request(owner, repo, title, head, base, body, author)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_GITHUB_PULL_CREATE}: {title}")
        args: dict[str, Any] = {
            "params": {"owner": owner, "repo": repo},
            "body": {
                "title": title,
                "head": head,
                "base": base,
                "body": body,
            },
        }

        try:
            result = self._swx.tools.execute(TOOL_GITHUB_PULL_CREATE, args)
            # Check if Swytchcode returned an API error response in result or data dict
            is_api_err = False
            err_text = ""
            inner_data = {}
            if isinstance(result, dict):
                inner_data = result.get("data", {})
                status_code = result.get("status_code")
                data_status = inner_data.get("status") if isinstance(inner_data, dict) else None
                if status_code in (400, 403, 404, 422) or data_status in (400, 403, 404, 422, "400", "403", "404", "422"):
                    is_api_err = True
                    err_text = str(result)
                elif "error" in result:
                    is_api_err = True
                    err_text = str(result.get("error"))

            if is_api_err:
                if "already exists" in err_text.lower() or "validation failed" in err_text.lower():
                    existing = self._find_existing_pull_request(owner, repo, head)
                    if existing:
                        logger.info(f"[TOOL] Reusing existing Pull Request #{existing.get('number')} for branch {head}")
                        return existing
                err_msg = inner_data.get("message", err_text) if isinstance(inner_data, dict) else err_text
                raise RuntimeError(f"Swytchcode GitHub PR creation error: {err_msg}")

            data = result.get("data", result) if isinstance(result, dict) else result
            if isinstance(data, dict):
                pr_num = data.get("number") or result.get("number")
                html_url = data.get("html_url") or result.get("html_url")
                pr_title = data.get("title") or result.get("title") or title
                pr_state = data.get("state") or result.get("state") or "open"
                if pr_num:
                    result["number"] = pr_num
                if html_url:
                    result["html_url"] = html_url
                if pr_title:
                    result["title"] = pr_title
                if pr_state:
                    result["state"] = pr_state
            logger.info(f"[TOOL] GitHub PR created via Swytchcode: #{result.get('number', 'OK')}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode GitHub PR creation failed: {err_msg}")
            if "already exists" in err_msg.lower() or "validation failed" in err_msg.lower():
                existing = self._find_existing_pull_request(owner, repo, head)
                if existing:
                    logger.info(f"[TOOL] Reusing existing Pull Request #{existing.get('number')} for branch {head}")
                    return existing
            raise RuntimeError(f"Swytchcode GitHub PR creation error: {err_msg}")

    def _find_existing_pull_request(self, owner: str, repo: str, head: str) -> Optional[dict[str, Any]]:
        """Look up existing open pull request for head branch."""
        import urllib.request as _req
        import urllib.error as _uerr

        token = os.getenv("GITHUB_TOKEN")
        clean_head = head.split(":")[-1]
        head_filter = f"{owner}:{clean_head}"
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?head={head_filter}&state=open"
        req = _req.Request(url)
        req.add_header("User-Agent", "DevPilot-Agent/1.0")
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with _req.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and data:
                    pr = data[0]
                    return {
                        "number": pr.get("number"),
                        "html_url": pr.get("html_url"),
                        "title": pr.get("title"),
                        "state": pr.get("state", "open"),
                        "head": {"ref": clean_head},
                        "base": {"ref": pr.get("base", {}).get("ref", "main")},
                        "data": pr,
                    }
        except Exception as e:
            logger.warning(f"Could not find existing PR via head filter for {head}: {e}")

        # Fallback: scan recent open PRs directly
        try:
            url_all = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page=15"
            req_all = _req.Request(url_all)
            req_all.add_header("User-Agent", "DevPilot-Agent/1.0")
            req_all.add_header("Accept", "application/vnd.github+json")
            if token:
                req_all.add_header("Authorization", f"Bearer {token}")
            with _req.urlopen(req_all, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    for pr in data:
                        pr_head_ref = pr.get("head", {}).get("ref", "")
                        if pr_head_ref in (clean_head, head):
                            return {
                                "number": pr.get("number"),
                                "html_url": pr.get("html_url"),
                                "title": pr.get("title"),
                                "state": pr.get("state", "open"),
                                "head": {"ref": pr_head_ref},
                                "base": {"ref": pr.get("base", {}).get("ref", "main")},
                                "data": pr,
                            }
        except Exception as e:
            logger.warning(f"Could not list open PRs for {owner}/{repo}: {e}")
        return None

    # =========================================================================
    # Jira Task Tracking Tools
    # =========================================================================

    def create_jira_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        priority: str = "High",
        issue_type: str = "Bug",
        github_issue_number: Optional[int] = None,
        pull_request_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a Jira issue using Swytchcode jira.api.issue.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Jira issue creation in {project_key}")
            return self._mock_jira_issue(
                project_key, summary, priority, issue_type, github_issue_number, pull_request_number
            )

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_JIRA_CREATE_ISSUE} in {project_key}")
        args: dict[str, Any] = {
            "body": {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": description}],
                            }
                        ],
                    },
                    "issuetype": {"name": issue_type},
                    "priority": {"name": priority},
                }
            }
        }

        try:
            result = self._swx.tools.execute(TOOL_JIRA_CREATE_ISSUE, args)
            logger.info(f"[TOOL] Jira task created via Swytchcode: {result.get('key', 'OK')}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode Jira execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode Jira error: {err_msg}")

    # =========================================================================
    # Slack Communication Tools
    # =========================================================================

    def send_slack_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Send a notification using Swytchcode slack.chat.postmessage.create."""
        if self.is_mock():
            logger.info(f"[TOOL] [MOCK] Simulating Slack notification to {channel}")
            return self._mock_slack_message(channel, text)

        logger.info(f"[TOOL] Executing Swytchcode tool {TOOL_SLACK_POST_MESSAGE} to {channel}")
        slack_body: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }
        if blocks:
            slack_body["blocks"] = blocks

        args: dict[str, Any] = {"body": slack_body}

        try:
            result = self._swx.tools.execute(TOOL_SLACK_POST_MESSAGE, args)
            data = result.get("data", result) if isinstance(result, dict) else result
            if isinstance(data, dict):
                is_ok = data.get("ok", False)
                if not is_ok:
                    slack_err = data.get("error", "Unknown Slack error")
                    raise RuntimeError(f"Slack API error: {slack_err}")
                if isinstance(result, dict):
                    result["delivered"] = True
                    result["ok"] = True
                    result["channel"] = channel
            logger.info(f"[TOOL] Slack notification delivered via Swytchcode to {channel}")
            return result
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[TOOL] Swytchcode Slack execution failed: {err_msg}")
            raise RuntimeError(f"Swytchcode Slack error: {err_msg}")

    # =========================================================================
    # Mock / Demo Implementations
    # =========================================================================

    def _mock_github_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """High-fidelity mock issues matching Swytchcode output schema."""
        return [
            {
                "id": 1001,
                "number": 101,
                "title": "[SECURITY] Remote authentication token leakage in OAuth callback",
                "body": (
                    "CRITICAL: User session tokens are inadvertently logged in plain text "
                    "during OAuth callback redirections in src/auth/oauth_handler.py. This exposes authenticated accounts "
                    "to unauthorized session hijacking in shared log aggregators."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/101",
                "user": {"login": "sec-auditor"},
                "labels": [{"name": "security"}, {"name": "critical"}, {"name": "cve"}],
                "state": "open",
                "comments": 4,
                "file_path": "src/auth/oauth_handler.py",
                "created_at": "2026-09-25T14:20:00Z",
                "updated_at": "2026-09-26T08:15:00Z",
            },
            {
                "id": 1002,
                "number": 102,
                "title": "[BUG] Payment API returns HTTP 500 on international credit card checkouts",
                "body": (
                    "Production incident: The payment processing gateway in src/services/payment_service.py fails with an "
                    "unhandled 500 Internal Server Error when processing non-USD currencies. "
                    "Root cause is floating point division precision without Decimal conversion."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/102",
                "user": {"login": "ops-lead"},
                "labels": [{"name": "bug"}, {"name": "p0"}, {"name": "payments"}],
                "state": "open",
                "comments": 12,
                "file_path": "src/services/payment_service.py",
                "created_at": "2026-09-25T18:45:00Z",
                "updated_at": "2026-09-26T07:30:00Z",
            },
            {
                "id": 1003,
                "number": 103,
                "title": "[PERF] High memory consumption in WebSocket connection pool",
                "body": (
                    "Under sustained load of >5,000 concurrent client connections, the "
                    "real-time event broker in src/realtime/broker.py leaks file descriptors."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/103",
                "user": {"login": "perf-eng"},
                "labels": [{"name": "performance"}, {"name": "backend"}],
                "state": "open",
                "comments": 3,
                "file_path": "src/realtime/broker.py",
                "created_at": "2026-09-24T11:10:00Z",
                "updated_at": "2026-09-25T16:00:00Z",
            },
            {
                "id": 1004,
                "number": 104,
                "title": "[DOCS] Update API setup guide for Python 3.12 compatibility",
                "body": (
                    "The local setup guide in docs/setup.md mentions python 3.10 and has an outdated reference."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/104",
                "user": {"login": "contributor-42"},
                "labels": [{"name": "documentation"}, {"name": "good-first-issue"}],
                "state": "open",
                "comments": 1,
                "file_path": "docs/setup.md",
                "created_at": "2026-09-23T09:00:00Z",
                "updated_at": "2026-09-23T10:00:00Z",
            },
            {
                "id": 1005,
                "number": 105,
                "title": "[FEATURE] Add dark mode theme switcher to settings panel",
                "body": (
                    "Users have requested a toggle between Light, Dark, and System theme "
                    "in src/components/ThemeToggle.tsx."
                ),
                "html_url": f"https://github.com/{owner}/{repo}/issues/105",
                "user": {"login": "designer-amy"},
                "labels": [{"name": "enhancement"}, {"name": "frontend"}],
                "state": "open",
                "comments": 2,
                "file_path": "src/components/ThemeToggle.tsx",
                "created_at": "2026-09-22T15:30:00Z",
                "updated_at": "2026-09-24T12:00:00Z",
            },
        ]

    def _mock_repository_file(self, path: str) -> dict[str, Any]:
        """Realistic codebase files for inspection and debugging."""
        codebase = {
            "src/services/payment_service.py": (
                "# Payment Processing Gateway Service\n"
                "from decimal import Decimal\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def process_transaction(amount, currency, exchange_rate):\n"
                "    # BUGGY CODE: causes float precision crash on non-USD\n"
                "    converted = float(amount) / exchange_rate\n"
                "    if converted <= 0:\n"
                "        raise ValueError('Invalid transaction amount')\n"
                "    # Charge credit card gateway\n"
                "    return {'status': 'processed', 'amount': converted, 'currency': currency}\n"
            ),
            "src/auth/oauth_handler.py": (
                "# OAuth Authentication Callback Handler\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def handle_oauth_callback(auth_code, token_response):\n"
                "    # SECURITY VULNERABILITY: Raw access token logged to shared aggregator\n"
                "    access_token = token_response.get('access_token')\n"
                "    logger.info(f'OAuth callback successful! Token: {access_token}')\n"
                "    return {'authenticated': True, 'token': access_token}\n"
            ),
            "src/components/ThemeToggle.tsx": (
                "// Theme Switcher Component\n"
                "import React, { useState } from 'react';\n\n"
                "export const ThemeToggle = () => {\n"
                "  const [theme, setTheme] = useState('light');\n"
                "  return <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>Toggle Theme</button>;\n"
                "};\n"
            ),
            "src/realtime/broker.py": (
                "# Realtime WebSocket Event Broker\n"
                "import asyncio\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "class ConnectionPool:\n"
                "    def __init__(self):\n"
                "        self.connections = []\n\n"
                "    def add(self, ws):\n"
                "        # BUGGY CODE: keeps appending sockets without cleanup or heartbeat check\n"
                "        self.connections.append(ws)\n\n"
                "    def broadcast(self, message):\n"
                "        for ws in self.connections:\n"
                "            ws.send(message)\n"
            ),
            "src/utils/file_manager.py": (
                "# Configuration File Reader & Storage Utility\n"
                "import os\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def read_service_config(config_path):\n"
                "    # RESOURCE LEAK (CWE-775): Unclosed file descriptor\n"
                "    f = open(config_path, 'r')\n"
                "    data = f.read()\n"
                "    return data\n"
            ),
            "src/database/query_builder.py": (
                "# Database Query Builder Service\n"
                "import sqlite3\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def get_user_account(account_id, db_conn):\n"
                "    # SECURITY VULNERABILITY (CWE-89): SQL Injection via string interpolation\n"
                "    query = f\"SELECT * FROM user_accounts WHERE account_id = '{account_id}'\"\n"
                "    cursor = db_conn.cursor()\n"
                "    cursor.execute(query)\n"
                "    return cursor.fetchone()\n"
            ),
            "src/api/user_service.py": (
                "# User Session & Role Manager\n"
                "import logging\n\n"
                "logger = logging.getLogger(__name__)\n\n"
                "def assign_user_roles(username, roles=[]):\n"
                "    # CODE DEFECT (PEP-484): Mutable default argument leaks roles across requests\n"
                "    roles.append('standard_user')\n"
                "    logger.info(f'Assigned roles to {username}')\n"
                "    return {'user': username, 'roles': roles}\n"
            ),
        }
        content = codebase.get(
            path,
            f"# Source file: {path}\n# Module placeholder\ndef handler():\n    return True\n"
        )
        return {
            "name": os.path.basename(path),
            "path": path,
            "sha": "mock-sha-blob-8831",
            "size": len(content),
            "type": "file",
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "encoding": "base64",
            "raw_text": content,
        }

    _global_pr_seq = 100

    def _mock_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str, author: str = "nikhil-mutreja"
    ) -> dict[str, Any]:
        """Realistic mock GitHub Pull Request creation with strictly unique numbers."""
        SwytchcodeClient._global_pr_seq += 1
        pr_number = SwytchcodeClient._global_pr_seq
        return {
            "id": 80000 + pr_number,
            "number": pr_number,
            "title": title,
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            "state": "open",
            "user": {"login": author, "html_url": f"https://github.com/{author}"},
            "head": {"ref": head, "label": f"{author}:{head}"},
            "base": {"ref": base, "label": f"{owner}:{base}"},
            "body": body,
            "created_at": "2026-09-26T09:59:00Z",
        }

    def _mock_jira_issue(
        self,
        project_key: str,
        summary: str,
        priority: str,
        issue_type: str,
        github_issue_number: Optional[int],
        pull_request_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """Realistic mock Jira issue creation response."""
        issue_num = github_issue_number or int(time.time() % 1000)
        key = f"{project_key}-{100 + issue_num}"
        return {
            "id": str(20000 + issue_num),
            "key": key,
            "self": f"https://mock-company.atlassian.net/rest/api/3/issue/{key}",
            "summary": summary,
            "priority": priority,
            "issue_type": issue_type,
            "status": "In Progress" if pull_request_number else "Created",
            "url": f"https://mock-company.atlassian.net/browse/{key}",
            "github_issue_number": issue_num,
            "pull_request_number": pull_request_number,
        }

    def _mock_slack_message(self, channel: str, text: str) -> dict[str, Any]:
        """Realistic mock Slack postMessage response."""
        return {
            "ok": True,
            "channel": channel,
            "ts": f"{int(time.time())}.012400",
            "message": {
                "text": text,
                "username": "DevPilot-AI-Engineer",
                "bot_id": "B08SWYTCH01",
                "type": "message",
            },
        }
