"""
API Contract Debugger — OpenEnv Environment

An AI agent receives a broken OpenAPI-style spec and must fix all contract
violations by proposing targeted field-level corrections step-by-step.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional

from openenv.core.env_server.interfaces import Environment

from .fixtures import TASKS
from .graders import detect_violations, grade_episode, step_reward
from .models import (
    ActionKind,
    DebugAction,
    DebugObservation,
    DebugState,
)


class APIContractDebuggerEnv(Environment[DebugAction, DebugObservation, DebugState]):
    """
    Environment where an agent debugs broken API contract specifications.

    Tasks (difficulty):
        easy   — 1 endpoint, 1 missing field
        medium — 3 endpoints, 3 violations (type errors + wrong status)
        hard   — 4 endpoints, 6 violations (missing fields, wrong types,
                 wrong status, forbidden extra field)

    Action space:
        DebugAction with kind in {add_field, remove_field, change_type,
                                  change_status, no_op}

    Observation space:
        DebugObservation — current endpoints + violation list + reward signals

    Reward:
        Dense per-step: +0.2×severity per violation fixed, -0.15×severity per
        violation introduced, -0.05 for malformed action.
        Episode terminates when all violations are resolved or max_steps reached.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(self, task_name: str = "easy") -> None:
        super().__init__()
        if task_name not in TASKS:
            raise ValueError(
                f"Unknown task '{task_name}'. Choose from: {list(TASKS.keys())}"
            )
        self._task_name = task_name
        self._task_cfg = TASKS[task_name]

        # Internal state (populated on reset)
        self._current_endpoints: List[Dict[str, Any]] = []
        self._golden_endpoints: List[Dict[str, Any]] = []
        self._original_endpoints: List[Dict[str, Any]] = []
        self._violations: List[Dict[str, Any]] = []
        self._initial_violations: List[Dict[str, Any]] = []
        self._step_count: int = 0
        self._episode_id: Optional[str] = None
        self._done: bool = False

    # ------------------------------------------------------------------
    # OpenEnv API
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_name: Optional[str] = None,
        **kwargs: Any,
    ) -> DebugObservation:
        """Reset the environment and return the initial observation."""
        if task_name and task_name in TASKS:
            self._task_name = task_name
            self._task_cfg = TASKS[task_name]

        self._episode_id = episode_id or str(uuid.uuid4())
        self._step_count = 0
        self._done = False

        # Deep-copy fixtures so mutations don't bleed across episodes
        self._current_endpoints = copy.deepcopy(self._task_cfg["broken_endpoints"])
        self._golden_endpoints = copy.deepcopy(self._task_cfg["golden_endpoints"])
        self._original_endpoints = copy.deepcopy(self._task_cfg["broken_endpoints"])

        self._violations = detect_violations(
            self._current_endpoints, self._golden_endpoints
        )
        self._initial_violations = copy.deepcopy(self._violations)

        return self._make_observation(
            reward=0.0,
            done=False,
            fixed_this_step=0,
            introduced_this_step=0,
            action_error=None,
        )

    def step(
        self,
        action: DebugAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> DebugObservation:
        """Apply one fix action and return the updated observation."""
        if self._done:
            return self._make_observation(
                reward=0.0,
                done=True,
                fixed_this_step=0,
                introduced_this_step=0,
                action_error="Episode is already done. Call reset().",
            )

        self._step_count += 1
        prev_violations = copy.deepcopy(self._violations)
        action_error: Optional[str] = None

        # --- Apply the action ---
        if action.kind == ActionKind.NO_OP:
            pass  # agent explicitly passes — small implicit penalty via no reward
        else:
            action_error = self._apply_action(action)

        # --- Recompute violations ---
        self._violations = detect_violations(
            self._current_endpoints, self._golden_endpoints
        )

        # --- Compute reward ---
        reward = step_reward(
            prev_violations=prev_violations,
            new_violations=self._violations,
            initial_violations=self._initial_violations,
            action_error=(action_error is not None),
        )

        fixed_this_step = sum(
            1 for v in prev_violations
            if v not in self._violations
        )
        introduced_this_step = sum(
            1 for v in self._violations
            if v not in prev_violations
        )

        # --- Termination ---
        max_steps = self._task_cfg["max_steps"]
        all_fixed = len(self._violations) == 0
        out_of_steps = self._step_count >= max_steps
        self._done = all_fixed or out_of_steps

        # Bonus reward for solving all violations
        if all_fixed:
            reward += 0.5

        return self._make_observation(
            reward=reward,
            done=self._done,
            fixed_this_step=fixed_this_step,
            introduced_this_step=introduced_this_step,
            action_error=action_error,
        )

    @property
    def state(self) -> DebugState:
        """Return the full internal environment state."""
        return DebugState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            task_name=self._task_name,
            original_endpoints=self._original_endpoints,
            current_endpoints=self._current_endpoints,
            golden_endpoints=self._golden_endpoints,
            violations=self._violations,
            total_violations_at_start=len(self._initial_violations),
            max_steps=self._task_cfg["max_steps"],
        )

    def get_metadata(self):
        from openenv.core.env_server.types import EnvironmentMetadata
        return EnvironmentMetadata(
            name="APIContractDebugger",
            description=(
                "An environment where an AI agent debugs broken OpenAPI-style "
                "contract specifications by proposing targeted field-level fixes."
            ),
            version="1.0.0",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_action(self, action: DebugAction) -> Optional[str]:
        """
        Mutate self._current_endpoints according to the action.
        Returns an error string if the action is invalid, else None.
        """
        idx = action.endpoint_index
        if idx < 0 or idx >= len(self._current_endpoints):
            return (
                f"endpoint_index {idx} is out of range "
                f"(0–{len(self._current_endpoints) - 1})"
            )

        endpoint = self._current_endpoints[idx]

        if action.kind == ActionKind.CHANGE_STATUS:
            if not isinstance(action.new_value, int):
                return "CHANGE_STATUS requires new_value to be an integer HTTP status code"
            endpoint["status_code"] = action.new_value
            return None

        # For field-level actions, validate location
        if action.location not in ("request_body", "response_body"):
            return (
                f"location must be 'request_body' or 'response_body', "
                f"got '{action.location}'"
            )

        body: Dict[str, Any] = endpoint.setdefault(action.location, {})
        field = action.field_name

        if action.kind == ActionKind.ADD_FIELD:
            if not field:
                return "ADD_FIELD requires a non-empty field_name"
            if not isinstance(action.new_value, dict) or "type" not in action.new_value:
                return "ADD_FIELD requires new_value to be a dict with a 'type' key"
            body[field] = action.new_value
            return None

        if action.kind == ActionKind.REMOVE_FIELD:
            if not field:
                return "REMOVE_FIELD requires a non-empty field_name"
            if field not in body:
                return f"field '{field}' does not exist in {action.location}"
            del body[field]
            return None

        if action.kind == ActionKind.CHANGE_TYPE:
            if not field:
                return "CHANGE_TYPE requires a non-empty field_name"
            if field not in body:
                return f"field '{field}' does not exist in {action.location}"
            if not isinstance(action.new_value, str):
                return "CHANGE_TYPE requires new_value to be a type string"
            body[field]["type"] = action.new_value
            return None

        return f"Unknown action kind: {action.kind}"

    def _make_observation(
        self,
        reward: float,
        done: bool,
        fixed_this_step: int,
        introduced_this_step: int,
        action_error: Optional[str],
    ) -> DebugObservation:
        return DebugObservation(
            task_name=self._task_name,
            task_description=self._task_cfg["description"],
            endpoints=copy.deepcopy(self._current_endpoints),
            violations=copy.deepcopy(self._violations),
            violations_fixed_this_step=fixed_this_step,
            violations_introduced_this_step=introduced_this_step,
            total_violations_at_start=len(self._initial_violations),
            step_count=self._step_count,
            max_steps=self._task_cfg["max_steps"],
            last_action_error=action_error,
            reward=reward,
            done=done,
        )

    def score(self) -> float:
        """Final episode score in [0.0, 1.0]. Call after episode ends."""
        return grade_episode(
            self._current_endpoints,
            self._golden_endpoints,
            self._initial_violations,
        )
