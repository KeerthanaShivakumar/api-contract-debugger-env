# Reinforcement Learning Architecture: API Contract Debugger

## Overview

The API Contract Debugger is a **reinforcement learning environment** built on the OpenEnv framework. It challenges AI agents to fix broken OpenAPI-style contract specifications by proposing targeted field-level corrections.

This document explains how the codebase implements the core RL concepts:
- **Agent** — The external AI system interacting with the environment
- **Environment** — The `APIContractDebuggerEnv` class that simulates the debugging task
- **State** — What the agent observes and the internal environment state
- **Action** — The fixes the agent can propose
- **Reward/Result** — The feedback signal and scoring mechanism

---

## 1. Agent (External AI System)

### What is the Agent?

The **agent** is an **external AI system** (e.g., an LLM, RL policy, or human) that:
- Receives observations from the environment
- Proposes actions (fixes to the API spec)
- Receives reward feedback and the next state
- Aims to maximize cumulative reward by fixing all violations

### Agent Interaction Pattern

```
Agent                              Environment
  |                                     |
  |---- POST /reset (task_name) ----->  |
  |                                     |
  | <------ Initial Observation --------| 
  |  (endpoints, violations, reward=0)  |
  |                                     |
  |---- POST /step (action) ----------> |
  |                                     |
  | <---- Updated Observation --------- |
  |  (new endpoints, new violations,    |
  |   reward, done, fixed/introduced)   |
  |                                     |
  | [repeat until done=True]            |
  |                                     |
  | ---- GET /score - GET /state ----->  |
  |                                     |
```

### Agent Location in Codebase

- **File**: `server/app.py`
- **Routes**: 
  - `POST /reset` — Initialize new episode
  - `POST /step` — Apply one action
  - `GET /state` — Query full environment state (for debugging)
  - `GET /score` — Get final episode score
  - `GET /tasks` — List available tasks

The agent communicates via HTTP REST API. All observations are JSON and fully serializable.

---

## 2. Environment (`APIContractDebuggerEnv`)

### Class Definition

**File**: `server/environment.py`

```python
class APIContractDebuggerEnv(Environment[DebugAction, DebugObservation, DebugState]):
    """
    Environment where an agent debugs broken API contract specifications.
    
    Inherits from OpenEnv's Environment base class.
    Implements reset(), step(), and state property.
    """
```

### Environment Responsibilities

1. **Initialize tasks** — Load broken + golden endpoint specs from fixtures
2. **Detect violations** — Compare current spec against golden spec
3. **Apply actions** — Mutate the current spec based on agent's fix proposal
4. **Compute rewards** — Dense per-step reward based on violations fixed/introduced
5. **Track state** — Maintain episode counter, step count, violations
6. **Terminate episodes** — Check for success (all fixed) or max steps reached

### Key Methods

#### `reset(seed, episode_id, task_name, **kwargs) → DebugObservation`

Initializes a fresh episode:
- Loads task config from fixtures
- Deep-copies broken endpoints to avoid cross-episode state leakage
- Detects initial violations
- Returns initial observation with reward=0

```python
def reset(self, seed=None, episode_id=None, task_name=None, **kwargs):
    """
    Reset the environment and return the initial observation.
    """
    # Load task config and deep-copy endpoints
    self._current_endpoints = copy.deepcopy(self._task_cfg["broken_endpoints"])
    self._golden_endpoints = copy.deepcopy(self._task_cfg["golden_endpoints"])
    
    # Detect violations (agent's starting problem)
    self._violations = detect_violations(self._current_endpoints, self._golden_endpoints)
    
    return self._make_observation(reward=0.0, done=False, ...)
```

#### `step(action, timeout_s, **kwargs) → DebugObservation`

Processes one agent action and returns the updated state:

```python
def step(self, action: DebugAction, **kwargs) -> DebugObservation:
    """
    Apply one fix action → return updated observation + reward.
    """
    # 1. Apply the action (mutate current_endpoints)
    action_error = self._apply_action(action)
    
    # 2. Recompute violations
    self._violations = detect_violations(self._current_endpoints, self._golden_endpoints)
    
    # 3. Compute dense reward
    reward = step_reward(prev_violations, self._violations, action_error)
    
    # 4. Check termination
    all_fixed = len(self._violations) == 0
    out_of_steps = self._step_count >= max_steps
    self._done = all_fixed or out_of_steps
    
    # 5. Bonus reward if solved
    if all_fixed:
        reward += 0.5
    
    return self._make_observation(reward, done, fixed_this_step, ...)
```

#### `_apply_action(action) → Optional[str]`

Attempts to mutate `self._current_endpoints` according to the action:

- **Validates** endpoint index, field name, locations
- **Executes** the fix:
  - `ADD_FIELD` — Insert new field into request/response body
  - `REMOVE_FIELD` — Delete field from body
  - `CHANGE_TYPE` — Update field's type
  - `CHANGE_STATUS` — Update endpoint's HTTP status code
  - `NO_OP` — Explicit pass (implicit penalty via no reward)
- **Returns** error string if invalid, `None` on success

#### `state` Property

Returns the complete internal state (not exposed to agent by default, but available via `/state`):

```python
@property
def state(self) -> DebugState:
    """Return full internal environment state."""
    return DebugState(
        episode_id=self._episode_id,
        step_count=self._step_count,
        task_name=self._task_name,
        original_endpoints=self._original_endpoints,     # Snapshot of broken spec
        current_endpoints=self._current_endpoints,       # Current state after fixes
        golden_endpoints=self._golden_endpoints,         # Target spec
        violations=self._violations,                     # Current violations
        total_violations_at_start=len(self._initial_violations),
        max_steps=self._task_cfg["max_steps"],
    )
```

### Supported Tasks

**File**: `server/fixtures.py`

Three difficulty levels:

| Task | Difficulty | Endpoints | Violations | Max Steps | Description |
|------|-----------|-----------|-----------|-----------|-------------|
| **easy** | Beginner | 1 | 1 missing field | 5 | Simple: add one field to response |
| **medium** | Intermediate | 3 | 3 (type errors + wrong status) | 10 | Type mismatches and HTTP status fixes |
| **hard** | Advanced | 4 | 6 (missing, extra, type, status) | 15 | Complex: multiple violation types |

Each task has:
- `broken_endpoints` — Starting state (what agent sees)
- `golden_endpoints` — Ground truth (what violations are measured against)
- `description` — Human-readable task objective
- `max_steps` — Episode cut-off

---

## 3. State

### Observation (`DebugObservation`)

**What the agent sees after each action.**

File: `server/models.py`

```python
class DebugObservation(Observation):
    """
    What the agent observes after reset() or step().
    """
    # Task info
    task_name: str                          # "easy" | "medium" | "hard"
    task_description: str                   # Human description
    
    # Current spec
    endpoints: List[Dict[str, Any]]         # Current endpoints (partially fixed)
    violations: List[Dict[str, Any]]        # Detected violations still present
    
    # Reward signals
    reward: float                           # Dense per-step reward
    done: bool                              # Episode termination flag
    violations_fixed_this_step: int         # Count of fixed violations
    violations_introduced_this_step: int    # Count of new violations
    total_violations_at_start: int          # Reference baseline
    
    # Tracking
    step_count: int                         # Steps taken so far
    max_steps: int                          # Episode limit
    last_action_error: Optional[str]        # Validation error message
```

#### Example Observation

```json
{
  "task_name": "easy",
  "task_description": "Add missing 'created_at' field to response...",
  "endpoints": [
    {
      "method": "POST",
      "path": "/users/register",
      "status_code": 201,
      "request_body": {
        "username": {"type": "string", "required": true},
        "email": {"type": "string", "required": true},
        "password": {"type": "string", "required": true}
      },
      "response_body": {
        "user_id": {"type": "integer", "required": true},
        "username": {"type": "string", "required": true}
        // missing: created_at
      }
    }
  ],
  "violations": [
    {
      "endpoint_index": 0,
      "location": "response_body",
      "field_name": "created_at",
      "violation_type": "missing_field",
      "description": "POST /users/register response_body: required field 'created_at' (string) is missing",
      "severity": 1.0
    }
  ],
  "violations_fixed_this_step": 0,
  "violations_introduced_this_step": 0,
  "total_violations_at_start": 1,
  "step_count": 0,
  "max_steps": 5,
  "reward": 0.0,
  "done": false,
  "last_action_error": null
}
```

### Full Internal State (`DebugState`)

**Available via `GET /state` endpoint (for debugging/analysis, not given to agent by default).**

```python
class DebugState(State):
    """
    Full internal state (not exposed to agent by default).
    """
    task_name: str
    original_endpoints: List[Dict[str, Any]]  # Snapshot of broken spec
    current_endpoints: List[Dict[str, Any]]   # Mutated by agent's actions
    golden_endpoints: List[Dict[str, Any]]    # Ground truth
    violations: List[Dict[str, Any]]          # Computed violations
    total_violations_at_start: int
    max_steps: int
```

---

## 4. Action (`DebugAction`)

**What the agent can propose.**

File: `server/models.py`

```python
class DebugAction(Action):
    """
    A single fix proposed by the agent.
    The agent targets one endpoint + one field and proposes exactly one change.
    """
    
    kind: ActionKind                    # Type of fix
    endpoint_index: int                 # Which endpoint to fix (0-indexed)
    location: str                       # "request_body" | "response_body" | "status_code"
    field_name: Optional[str]           # Field to modify (null for status_code)
    new_value: Optional[Any]            # The corrected value
```

### Action Types (`ActionKind`)

| Kind | Target | Effect | new_value |
|------|--------|--------|-----------|
| `ADD_FIELD` | Field | Insert missing field into body | `{"type": str, "description"?: str}` |
| `REMOVE_FIELD` | Field | Delete forbidden field from body | `null` |
| `CHANGE_TYPE` | Field | Fix field's JSON Schema type | Type string (e.g., `"integer"`) |
| `CHANGE_STATUS` | Endpoint | Fix HTTP status code | Integer (e.g., `201`) |
| `NO_OP` | None | Explicit pass/wait | `null` |

#### Example Actions

```python
# Fix 1: Add missing 'created_at' field
{
  "kind": "add_field",
  "endpoint_index": 0,
  "location": "response_body",
  "field_name": "created_at",
  "new_value": {
    "type": "string",
    "description": "ISO-8601 timestamp"
  }
}

# Fix 2: Change field type from string to integer
{
  "kind": "change_type",
  "endpoint_index": 1,
  "location": "request_body",
  "field_name": "user_id",
  "new_value": "integer"
}

# Fix 3: Correct HTTP status code
{
  "kind": "change_status",
  "endpoint_index": 0,
  "location": "status_code",
  "field_name": null,
  "new_value": 201
}

# Fix 4: Remove extra field
{
  "kind": "remove_field",
  "endpoint_index": 2,
  "location": "response_body",
  "field_name": "deprecated_field",
  "new_value": null
}

# Fix 5: Explicit pass
{
  "kind": "no_op",
  "endpoint_index": 0,
  "location": "request_body",
  "field_name": null,
  "new_value": null
}
```

### Action Validation

The environment validates actions in `_apply_action()`:

- **Endpoint index bounds** — Must be `0 ≤ index < len(endpoints)`
- **Location validity** — Must be `"request_body"`, `"response_body"`, or `"status_code"`
- **Field existence** — REMOVE_FIELD and CHANGE_TYPE require field to exist
- **Type format** — Fields must have `{"type": "..."}` structure
- **Status code format** — Must be an integer

If validation fails, `_apply_action()` returns an error string and the step receives `-0.05` reward penalty.

---

## 5. Reward & Result

### Dense Per-Step Reward

**File**: `server/graders.py` → `step_reward()` function

The agent receives feedback after each step:

```python
def step_reward(
    prev_violations: List[Dict[str, Any]],
    new_violations: List[Dict[str, Any]],
    initial_violations: List[Dict[str, Any]],
    action_error: bool,
) -> float:
    """
    Dense per-step reward:
    +0.2 × severity  per violation resolved
    -0.15 × severity per new violation introduced
    -0.05             for malformed action
    +0.5              bonus if all violations fixed (episode success)
    """
    if action_error:
        return -0.05
    
    reward = 0.0
    for v in violations_fixed_this_step:
        reward += 0.2 * v["severity"]
    for v in violations_introduced_this_step:
        reward -= 0.15 * v["severity"]
    
    return reward
```

### Violation Severity Weights

Weighted by problem importance:

| Violation Type | Severity | Reason |
|----------------|----------|--------|
| `missing_field` | 1.0 | Breaks contract — top priority |
| `wrong_type` | 0.9 | Type mismatch — critical |
| `wrong_status` | 0.8 | HTTP code error — significant |
| `extra_field` | 0.7 | Forbidden field — less critical |

### Episode Scoring (`grade_episode()`)

**Computed at episode end.** Returns final score in `[0.0, 1.0]`.

```python
def grade_episode(
    current_endpoints: List[Dict[str, Any]],
    golden_endpoints: List[Dict[str, Any]],
    initial_violations: List[Dict[str, Any]],
) -> float:
    """
    Final episode score:
    
    score = (weighted_violations_fixed - weighted_violations_introduced) 
            / total_initial_weight
    
    Clamped to [0.0, 1.0]
    
    1.0 = all violations fixed, no new ones introduced
    0.5 = 50% of violations fixed
    0.0 = no improvement or made things worse
    """
```

#### Example Scoring Scenario

**Task: easy (1 violation)**
- Initial violation: `missing_field "created_at" (severity=1.0)`
- After 1 step: Agent adds `created_at` correctly
- After 2 steps: Agent incorrectly changes type of `username` to `integer` (introduces 1 violation)
- Final state: 0 remaining violations, but 1 introduced

```
score = (1.0 - 1.0) / 1.0 = 0.0
```

Clamped to 0.0 (agent made things worse overall).

---

## 6. Complete RL Loop Example

### Scenario: Easy Task

**Initial state:**
```
Broken spec: POST /users/register response missing "created_at"
Golden spec: response has user_id, username, created_at
```

### Episode Transcript

```
RESET request (task_name="easy")
  ↓
Observation #0:
  endpoints: [broken registration endpoint]
  violations: [missing_field "created_at"]
  reward: 0.0
  done: false
  step_count: 0

STEP 1: Agent proposes ADD_FIELD action
  action.kind = "add_field"
  action.endpoint_index = 0
  action.location = "response_body"
  action.field_name = "created_at"
  action.new_value = {"type": "string", "description": "ISO-8601 timestamp"}
  ↓
Environment:
  - Validates action ✓
  - Adds field to response_body
  - Recomputes violations → [] (0 violations!)
  - Computes reward: +0.2 × 1.0 (fixed 1 violation of severity 1.0) = +0.2
          + 0.5 (bonus for all_fixed=true) = +0.7 total
  - Sets done=true (all violations fixed)
  ↓
Observation #1:
  endpoints: [fixed registration endpoint]
  violations: []
  violations_fixed_this_step: 1
  violations_introduced_this_step: 0
  reward: 0.7
  done: true
  step_count: 1

SCORE request
  ↓
score = (1.0 fixed - 0 introduced) / 1.0 initial = 1.0 ✓

Agent succeeds with perfect score!
```

---

## 7. File Structure Summary

```
server/
├── app.py                    # FastAPI routes, HTTP interface
├── environment.py            # APIContractDebuggerEnv (core RL logic)
├── models.py                 # Pydantic models: DebugAction, DebugObservation, DebugState
├── fixtures.py               # Task definitions (easy, medium, hard)
├── graders.py                # Violation detection + reward/scoring
└── __pycache__/

tests/                         # Unit tests for environment, graders, fixtures

RL_ARCHITECTURE.md             # This file
```

---

## 8. Key Design Principles

1. **Stateful Environment** — One episode per task at a time (OpenEnv singleton pattern)

2. **Dense Rewards** — Agent gets per-step feedback (not just final score) to guide learning

3. **Severity-Weighted** — Different violation types have different weights (missing fields = highest priority)

4. **Action Validation** — Invalid actions receive penalty and return error messages

5. **Deep-Copied State** — Endpoints are deep-copied to prevent cross-episode contamination

6. **Observable Violations** — Agent sees exact list of violations (not hidden)

7. **Termination Conditions**:
   - Success: All violations fixed
   - Failure: Max steps exceeded

8. **JSON/REST Interface** — Agent communicates via HTTP (language-agnostic)

---

## 9. Typical Agent Workflow

```python
import requests

BASE_URL = "http://localhost:7860"

# 1. Reset to start new episode
reset_resp = requests.post(f"{BASE_URL}/reset", json={
    "task_name": "easy",
    "seed": 42
})
obs = reset_resp.json()
print(f"Violations to fix: {len(obs['violations'])}")

# 2. Repeat: observe → decide → act
for step in range(obs['max_steps']):
    if obs['done']:
        break
    
    # Agent decision logic (depends on obs['violations'])
    action = {
        "kind": "add_field",
        "endpoint_index": 0,
        "location": "response_body",
        "field_name": "created_at",
        "new_value": {"type": "string"}
    }
    
    # 3. Apply action
    step_resp = requests.post(f"{BASE_URL}/step", json={"action": action})
    obs = step_resp.json()
    
    print(f"Step {step+1}: reward={obs['reward']}, violations={len(obs['violations'])}")

# 4. Check final score
score_resp = requests.get(f"{BASE_URL}/score")
print(f"Final score: {score_resp.json()['score']}")
```

---

## 10. Future Extensions

Potential enhancements to the RL framework:

1. **Multi-Agent** — Support concurrent episodes via session IDs
2. **Curriculum Learning** — Dynamically adapt difficulty based on agent performance
3. **Partial Observability** — Hide some violations initially to increase challenge
4. **Action Constraints** — Limit action space per step (e.g., "fix at most 1 field")
5. **Custom Reward Shaping** — Configurable severity weights + bonus structures
6. **State Representation** — Multiple formats (JSON, graph, embedding-friendly)

---

## Summary Table

| Concept | Implementation | File | Purpose |
|---------|---|---|---|
| **Agent** | External AI/LLM | HTTP client | Proposes fixes |
| **Environment** | `APIContractDebuggerEnv` | `environment.py` | Simulates faults + validates fixes |
| **State** | `DebugObservation` + `DebugState` | `models.py` | Agent observes + internal tracking |
| **Action** | `DebugAction` | `models.py` | Fix proposals |
| **Reward** | `step_reward()` | `graders.py` | Dense per-step feedback |
| **Result** | Episode score `[0.0, 1.0]` | `graders.py` | Final performance metric |
| **Tasks** | Fixtures (easy/medium/hard) | `fixtures.py` | Problem instances |
| **HTTP API** | FastAPI routes | `app.py` | Communication interface |

