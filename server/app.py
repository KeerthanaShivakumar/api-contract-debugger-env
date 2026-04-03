"""
FastAPI application entry point for the API Contract Debugger OpenEnv environment.

Route registration order:
  1. Custom stateful /reset, /step, /state routes registered FIRST.
  2. OpenEnv PRODUCTION-mode routes (/health, /schema, /metadata, /ws) attached LAST.
     PRODUCTION mode does NOT register /reset /step /state, so our routes win.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from openenv.core.env_server.http_server import HTTPEnvServer
from openenv.core.env_server.types import ServerMode

from .environment import APIContractDebuggerEnv
from .models import DebugAction, DebugObservation, DebugState

# ---------------------------------------------------------------------------
# Singleton environment instances — one per task
# ---------------------------------------------------------------------------

_envs: Dict[str, APIContractDebuggerEnv] = {
    "easy":   APIContractDebuggerEnv(task_name="easy"),
    "medium": APIContractDebuggerEnv(task_name="medium"),
    "hard":   APIContractDebuggerEnv(task_name="hard"),
}

_active_task: str = "easy"


def _get_env() -> APIContractDebuggerEnv:
    return _envs[_active_task]


# ---------------------------------------------------------------------------
# Request bodies for our custom routes
# ---------------------------------------------------------------------------

class ResetBody(BaseModel):
    task_name: Optional[str] = Field(
        default=None,
        description="Task to run: 'easy', 'medium', or 'hard'.",
    )
    seed: Optional[int] = Field(default=None)
    episode_id: Optional[str] = Field(default=None)


class StepBody(BaseModel):
    action: Dict[str, Any] = Field(
        ...,
        description="Serialised DebugAction payload.",
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="API Contract Debugger",
        description=(
            "An OpenEnv environment where AI agents debug broken OpenAPI-style "
            "contract specifications by proposing targeted field-level fixes."
        ),
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # 1. Our stateful routes — registered FIRST
    # ------------------------------------------------------------------

    @app.get("/", tags=["API"])
    async def root() -> Dict[str, str]:
        """Root endpoint with API information."""
        return {
            "name": "API Contract Debugger",
            "description": "OpenEnv environment for debugging API contracts",
            "docs": "/docs",
            "version": "1.0.0"
        }

    @app.post("/reset", tags=["Environment"])
    async def reset(req: ResetBody = ResetBody()) -> Dict[str, Any]:
        """Reset the environment. Optionally switch task via task_name."""
        global _active_task
        if req.task_name is not None:
            if req.task_name not in _envs:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown task '{req.task_name}'. Choose: {list(_envs.keys())}",
                )
            _active_task = req.task_name

        obs: DebugObservation = _get_env().reset(
            seed=req.seed,
            episode_id=req.episode_id,
        )
        return obs.model_dump()

    @app.post("/step", tags=["Environment"])
    async def step(req: StepBody) -> Dict[str, Any]:
        """Apply one fix action and return the updated observation."""
        try:
            action = DebugAction.model_validate(req.action)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid action: {exc}")

        obs: DebugObservation = _get_env().step(action)
        return obs.model_dump()

    @app.get("/state", tags=["Environment"])
    async def state() -> Dict[str, Any]:
        """Return the full internal environment state."""
        s: DebugState = _get_env().state
        return s.model_dump()

    @app.get("/score", tags=["Environment"])
    async def score() -> Dict[str, Any]:
        """Return the final episode score [0.0, 1.0]."""
        return {
            "task": _active_task,
            "score": _get_env().score(),
        }

    @app.get("/tasks", tags=["Environment"])
    async def list_tasks() -> Dict[str, Any]:
        """List available tasks with descriptions."""
        from .fixtures import TASKS
        return {
            "tasks": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "max_steps": t["max_steps"],
                    "num_endpoints": len(t["broken_endpoints"]),
                }
                for t in TASKS.values()
            ]
        }

    # ------------------------------------------------------------------
    # 2. OpenEnv framework routes — registered LAST (PRODUCTION mode)
    #    Adds /health, /schema, /metadata, /ws ONLY.
    #    Does NOT override our /reset, /step, /state.
    # ------------------------------------------------------------------

    _server = HTTPEnvServer(
        env=_get_env,
        action_cls=DebugAction,
        observation_cls=DebugObservation,
    )
    _server.register_routes(app, mode=ServerMode.PRODUCTION)

    return app


app = create_app()

def main() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
