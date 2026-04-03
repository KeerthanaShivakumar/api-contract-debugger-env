"""
Test suite for the API Contract Debugger environment.

Coverage:
  - Violation detection (all violation types)
  - Grader scoring
  - Per-step reward shaping
  - Environment reset / step / state
  - All three tasks end-to-end
  - Edge cases: malformed actions, double-fix, already-clean spec
  - HTTP API routes (via TestClient)
"""

from __future__ import annotations

import copy
import sys
import os

import pytest

# Make sure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.fixtures import TASK_EASY, TASK_HARD, TASK_MEDIUM, TASKS
from server.graders import detect_violations, grade_episode, step_reward
from server.models import ActionKind, DebugAction
from server.environment import APIContractDebuggerEnv


# ===========================================================================
# Helpers
# ===========================================================================

def make_env(task: str = "easy") -> APIContractDebuggerEnv:
    env = APIContractDebuggerEnv(task_name=task)
    env.reset()
    return env


def action(**kwargs) -> DebugAction:
    defaults = dict(
        kind=ActionKind.NO_OP,
        endpoint_index=0,
        location="response_body",
        field_name=None,
        new_value=None,
    )
    defaults.update(kwargs)
    return DebugAction(**defaults)


# ===========================================================================
# 1. Fixture sanity
# ===========================================================================

class TestFixtures:
    def test_all_tasks_present(self):
        assert set(TASKS.keys()) == {"easy", "medium", "hard"}

    def test_easy_has_violations(self):
        v = detect_violations(TASK_EASY["broken_endpoints"], TASK_EASY["golden_endpoints"])
        assert len(v) == 1

    def test_medium_has_three_violations(self):
        v = detect_violations(TASK_MEDIUM["broken_endpoints"], TASK_MEDIUM["golden_endpoints"])
        assert len(v) == 3

    def test_hard_has_six_violations(self):
        v = detect_violations(TASK_HARD["broken_endpoints"], TASK_HARD["golden_endpoints"])
        assert len(v) == 6

    def test_golden_specs_are_clean(self):
        for task in TASKS.values():
            v = detect_violations(task["golden_endpoints"], task["golden_endpoints"])
            assert v == [], f"Golden spec for '{task['name']}' has violations: {v}"

    def test_broken_and_golden_same_length(self):
        for task in TASKS.values():
            assert len(task["broken_endpoints"]) == len(task["golden_endpoints"])


# ===========================================================================
# 2. Violation detection
# ===========================================================================

class TestViolationDetection:
    def test_missing_field_detected(self):
        current = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {}}]
        golden  = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {
                         "id": {"type": "integer", "required": True, "description": ""}
                     }}]
        v = detect_violations(current, golden)
        assert len(v) == 1
        assert v[0]["violation_type"] == "missing_field"
        assert v[0]["field_name"] == "id"

    def test_extra_field_detected(self):
        current = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {
                         "secret": {"type": "string", "required": False, "description": ""}
                     }}]
        golden  = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {}}]
        v = detect_violations(current, golden)
        assert len(v) == 1
        assert v[0]["violation_type"] == "extra_field"

    def test_wrong_type_detected(self):
        current = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {
                         "count": {"type": "string", "required": True, "description": ""}
                     }}]
        golden  = [{"method": "GET", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {
                         "count": {"type": "integer", "required": True, "description": ""}
                     }}]
        v = detect_violations(current, golden)
        assert len(v) == 1
        assert v[0]["violation_type"] == "wrong_type"

    def test_wrong_status_detected(self):
        current = [{"method": "DELETE", "path": "/x", "status_code": 200,
                     "request_body": {}, "response_body": {}}]
        golden  = [{"method": "DELETE", "path": "/x", "status_code": 204,
                     "request_body": {}, "response_body": {}}]
        v = detect_violations(current, golden)
        assert len(v) == 1
        assert v[0]["violation_type"] == "wrong_status"

    def test_no_violations_on_matching_spec(self):
        golden = TASK_EASY["golden_endpoints"]
        v = detect_violations(golden, golden)
        assert v == []

    def test_violation_severity_range(self):
        v = detect_violations(TASK_HARD["broken_endpoints"], TASK_HARD["golden_endpoints"])
        for viol in v:
            assert 0.0 < viol["severity"] <= 1.0


# ===========================================================================
# 3. Grader scoring
# ===========================================================================

class TestGrader:
    def test_perfect_score_when_all_fixed(self):
        golden = TASK_EASY["golden_endpoints"]
        initial = detect_violations(TASK_EASY["broken_endpoints"], golden)
        score = grade_episode(golden, golden, initial)
        assert score == pytest.approx(1.0)

    def test_zero_score_when_nothing_fixed(self):
        broken = TASK_EASY["broken_endpoints"]
        golden = TASK_EASY["golden_endpoints"]
        initial = detect_violations(broken, golden)
        score = grade_episode(broken, golden, initial)
        assert score == pytest.approx(0.0)

    def test_partial_score_medium(self):
        broken = copy.deepcopy(TASK_MEDIUM["broken_endpoints"])
        golden = TASK_MEDIUM["golden_endpoints"]
        initial = detect_violations(broken, golden)

        # Fix only violation 1: product_id type
        broken[0]["response_body"]["product_id"]["type"] = "integer"

        score = grade_episode(broken, golden, initial)
        assert 0.0 < score < 1.0

    def test_score_clamped_to_zero_when_extra_violations_introduced(self):
        broken = copy.deepcopy(TASK_EASY["broken_endpoints"])
        golden = TASK_EASY["golden_endpoints"]
        initial = detect_violations(broken, golden)

        # Introduce more violations
        broken[0]["response_body"]["user_id"]["type"] = "string"
        broken[0]["response_body"]["username"]["type"] = "boolean"

        score = grade_episode(broken, golden, initial)
        assert score == 0.0

    def test_score_in_range(self):
        for task in TASKS.values():
            broken = task["broken_endpoints"]
            golden = task["golden_endpoints"]
            initial = detect_violations(broken, golden)
            score = grade_episode(broken, golden, initial)
            assert 0.0 <= score <= 1.0, f"Out-of-range score for task '{task['name']}'"

    def test_already_clean_spec_scores_one(self):
        golden = TASK_EASY["golden_endpoints"]
        initial: list = []  # no violations at start
        score = grade_episode(golden, golden, initial)
        assert score == pytest.approx(1.0)


# ===========================================================================
# 4. Step reward
# ===========================================================================

class TestStepReward:
    def _make_violation(self, vtype="missing_field", severity=1.0):
        return {
            "endpoint_index": 0, "location": "response_body",
            "field_name": "foo", "violation_type": vtype,
            "description": "test", "severity": severity,
        }

    def test_positive_reward_for_fix(self):
        v = self._make_violation()
        r = step_reward(prev_violations=[v], new_violations=[], initial_violations=[v], action_error=False)
        assert r > 0

    def test_negative_reward_for_introduction(self):
        v = self._make_violation()
        r = step_reward(prev_violations=[], new_violations=[v], initial_violations=[], action_error=False)
        assert r < 0

    def test_penalty_for_action_error(self):
        r = step_reward(prev_violations=[], new_violations=[], initial_violations=[], action_error=True)
        assert r == pytest.approx(-0.05)

    def test_zero_reward_for_no_op(self):
        r = step_reward(prev_violations=[], new_violations=[], initial_violations=[], action_error=False)
        assert r == pytest.approx(0.0)


# ===========================================================================
# 5. Environment — reset
# ===========================================================================

class TestEnvReset:
    def test_reset_returns_observation(self):
        env = APIContractDebuggerEnv(task_name="easy")
        obs = env.reset()
        assert obs.task_name == "easy"
        assert len(obs.violations) == 1
        assert obs.done is False
        assert obs.step_count == 0

    def test_reset_clears_state(self):
        env = make_env("easy")
        # Take a step, then reset
        env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "string", "required": True, "description": "timestamp"},
        ))
        obs = env.reset()
        assert obs.step_count == 0
        assert len(obs.violations) == 1  # back to broken state

    def test_reset_switches_task(self):
        env = APIContractDebuggerEnv(task_name="easy")
        obs = env.reset(task_name="medium")
        assert obs.task_name == "medium"
        assert len(obs.violations) == 3

    def test_reset_preserves_golden(self):
        env = make_env("hard")
        obs = env.reset()
        assert obs.total_violations_at_start == 6

    def test_episode_id_set_on_reset(self):
        env = APIContractDebuggerEnv(task_name="easy")
        env.reset(episode_id="test-123")
        assert env.state.episode_id == "test-123"


# ===========================================================================
# 6. Environment — step mechanics
# ===========================================================================

class TestEnvStep:
    def test_add_missing_field_fixes_easy(self):
        env = make_env("easy")
        obs = env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "string", "required": True, "description": "ISO timestamp"},
        ))
        assert len(obs.violations) == 0
        assert obs.done is True
        assert obs.reward > 0

    def test_wrong_type_action_introduces_violation(self):
        env = make_env("easy")
        obs = env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "integer", "required": True, "description": "wrong type"},
        ))
        # Still has a violation (wrong type now)
        assert len(obs.violations) == 1
        assert obs.violations[0]["violation_type"] == "wrong_type"

    def test_out_of_range_endpoint_index(self):
        env = make_env("easy")
        obs = env.step(action(kind=ActionKind.ADD_FIELD, endpoint_index=99,
                               field_name="x", new_value={"type": "string"}))
        assert obs.last_action_error is not None
        assert "out of range" in obs.last_action_error

    def test_change_type_fixes_medium_violation(self):
        env = make_env("medium")
        # Fix violation 1: product_id type string→integer in response
        obs = env.step(action(
            kind=ActionKind.CHANGE_TYPE,
            endpoint_index=0,
            location="response_body",
            field_name="product_id",
            new_value="integer",
        ))
        assert obs.violations_fixed_this_step == 1
        assert len(obs.violations) == 2  # 2 remaining

    def test_change_status_fixes_medium_violation(self):
        env = make_env("medium")
        obs = env.step(action(
            kind=ActionKind.CHANGE_STATUS,
            endpoint_index=2,
            location="status_code",
            new_value=204,
        ))
        assert obs.violations_fixed_this_step == 1

    def test_remove_field_fixes_hard_extra_field(self):
        env = make_env("hard")
        obs = env.step(action(
            kind=ActionKind.REMOVE_FIELD,
            endpoint_index=1,
            location="response_body",
            field_name="password_hash",
        ))
        assert obs.violations_fixed_this_step == 1

    def test_no_op_does_not_change_violations(self):
        env = make_env("easy")
        before = len(env.state.violations)
        obs = env.step(action(kind=ActionKind.NO_OP))
        assert len(obs.violations) == before

    def test_step_after_done_returns_done(self):
        env = make_env("easy")
        # Solve it
        env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "string", "required": True, "description": "ts"},
        ))
        # Step again — should get done=True with error message
        obs = env.step(action(kind=ActionKind.NO_OP))
        assert obs.done is True
        assert obs.last_action_error is not None

    def test_max_steps_terminates_episode(self):
        env = APIContractDebuggerEnv(task_name="easy")
        env.reset()
        obs = None
        for _ in range(env._task_cfg["max_steps"]):
            obs = env.step(action(kind=ActionKind.NO_OP))
        assert obs.done is True

    def test_step_count_increments(self):
        env = make_env("easy")
        env.step(action(kind=ActionKind.NO_OP))
        env.step(action(kind=ActionKind.NO_OP))
        assert env.state.step_count == 2


# ===========================================================================
# 7. Environment — state
# ===========================================================================

class TestEnvState:
    def test_state_reflects_current_endpoints(self):
        env = make_env("easy")
        state = env.state
        assert len(state.current_endpoints) == 1
        assert state.task_name == "easy"

    def test_state_tracks_step_count(self):
        env = make_env("easy")
        env.step(action(kind=ActionKind.NO_OP))
        assert env.state.step_count == 1

    def test_original_endpoints_unchanged_after_steps(self):
        env = make_env("easy")
        original_before = copy.deepcopy(env.state.original_endpoints)
        env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "string", "required": True, "description": "ts"},
        ))
        assert env.state.original_endpoints == original_before


# ===========================================================================
# 8. Full episode walkthroughs
# ===========================================================================

class TestFullEpisodes:
    def test_easy_perfect_solve(self):
        env = make_env("easy")
        env.step(action(
            kind=ActionKind.ADD_FIELD,
            location="response_body",
            field_name="created_at",
            new_value={"type": "string", "required": True, "description": "ISO timestamp"},
        ))
        assert env.score() == pytest.approx(1.0)

    def test_medium_perfect_solve(self):
        env = make_env("medium")
        # Fix 1: product_id type
        env.step(action(kind=ActionKind.CHANGE_TYPE, endpoint_index=0,
                        location="response_body", field_name="product_id", new_value="integer"))
        # Fix 2: quantity type
        env.step(action(kind=ActionKind.CHANGE_TYPE, endpoint_index=1,
                        location="request_body", field_name="quantity", new_value="integer"))
        # Fix 3: DELETE status code
        env.step(action(kind=ActionKind.CHANGE_STATUS, endpoint_index=2,
                        location="status_code", new_value=204))
        assert env.score() == pytest.approx(1.0)

    def test_hard_perfect_solve(self):
        env = make_env("hard")
        # Fix 1: add refresh_token to /auth/login response
        env.step(action(kind=ActionKind.ADD_FIELD, endpoint_index=0,
                        location="response_body", field_name="refresh_token",
                        new_value={"type": "string", "required": True, "description": "Refresh token"}))
        # Fix 2: expires_in type string→integer in /auth/login response
        env.step(action(kind=ActionKind.CHANGE_TYPE, endpoint_index=0,
                        location="response_body", field_name="expires_in", new_value="integer"))
        # Fix 3: add created_at to /users/{id}/profile response
        env.step(action(kind=ActionKind.ADD_FIELD, endpoint_index=1,
                        location="response_body", field_name="created_at",
                        new_value={"type": "string", "required": True, "description": "ISO timestamp"}))
        # Fix 4: remove password_hash from /users/{id}/profile response
        env.step(action(kind=ActionKind.REMOVE_FIELD, endpoint_index=1,
                        location="response_body", field_name="password_hash"))
        # Fix 5: PATCH status 500→200
        env.step(action(kind=ActionKind.CHANGE_STATUS, endpoint_index=2,
                        location="status_code", new_value=200))
        # Fix 6: add updated_at to PATCH response
        env.step(action(kind=ActionKind.ADD_FIELD, endpoint_index=2,
                        location="response_body", field_name="updated_at",
                        new_value={"type": "string", "required": True, "description": "ISO timestamp"}))

        assert env.score() == pytest.approx(1.0)

    def test_score_after_partial_solve(self):
        env = make_env("medium")
        # Fix only 1 of 3
        env.step(action(kind=ActionKind.CHANGE_TYPE, endpoint_index=0,
                        location="response_body", field_name="product_id", new_value="integer"))
        score = env.score()
        assert 0.0 < score < 1.0

    def test_unknown_task_raises(self):
        with pytest.raises(ValueError, match="Unknown task"):
            APIContractDebuggerEnv(task_name="impossible")


# ===========================================================================
# 9. HTTP API routes (FastAPI TestClient)
# ===========================================================================

class TestHTTPRoutes:
    @pytest.fixture(autouse=True)
    def client(self):
        from fastapi.testclient import TestClient
        from server.app import app
        self.client = TestClient(app)

    def test_health_endpoint(self):
        r = self.client.get("/health")
        assert r.status_code == 200

    def test_reset_returns_200(self):
        r = self.client.post("/reset", json={})
        assert r.status_code == 200
        data = r.json()
        assert "violations" in data
        assert "endpoints" in data

    def test_reset_switches_task(self):
        r = self.client.post("/reset", json={"task_name": "medium"})
        assert r.status_code == 200
        assert r.json()["task_name"] == "medium"

    def test_reset_unknown_task_422(self):
        r = self.client.post("/reset", json={"task_name": "impossible"})
        assert r.status_code == 422

    def test_step_add_field(self):
        self.client.post("/reset", json={"task_name": "easy"})
        r = self.client.post("/step", json={
            "action": {
                "kind": "add_field",
                "endpoint_index": 0,
                "location": "response_body",
                "field_name": "created_at",
                "new_value": {"type": "string", "required": True, "description": "ts"},
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert data["done"] is True
        assert data["reward"] > 0

    def test_step_invalid_action_422(self):
        self.client.post("/reset", json={})
        r = self.client.post("/step", json={"action": {"kind": "nonexistent_kind"}})
        assert r.status_code == 422

    def test_state_endpoint(self):
        self.client.post("/reset", json={"task_name": "easy"})
        r = self.client.get("/state")
        assert r.status_code == 200
        assert "current_endpoints" in r.json()

    def test_score_endpoint(self):
        self.client.post("/reset", json={"task_name": "easy"})
        r = self.client.get("/score")
        assert r.status_code == 200
        data = r.json()
        assert "score" in data
        assert 0.0 <= data["score"] <= 1.0

    def test_tasks_endpoint(self):
        r = self.client.get("/tasks")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tasks"]) == 3

    def test_schema_endpoint(self):
        r = self.client.get("/schema")
        assert r.status_code == 200
        schema = r.json()
        assert "action" in schema
        assert "observation" in schema

    def test_full_easy_solve_via_http(self):
        self.client.post("/reset", json={"task_name": "easy"})
        r = self.client.post("/step", json={
            "action": {
                "kind": "add_field",
                "endpoint_index": 0,
                "location": "response_body",
                "field_name": "created_at",
                "new_value": {"type": "string", "required": True, "description": "ts"},
            }
        })
        assert r.json()["done"] is True
        score_r = self.client.get("/score")
        assert score_r.json()["score"] == pytest.approx(1.0)
