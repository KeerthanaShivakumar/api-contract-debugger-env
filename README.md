---
title: API Contract Debugger
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
tags:
  - openenv
  - rl-environment
  - api-debugging
  - contract-testing
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# API Contract Debugger — OpenEnv Environment

An OpenEnv environment where AI agents debug broken OpenAPI-style contract
specifications by proposing targeted field-level corrections.

## What Is This?

Every backend engineer debugs API contract violations constantly — mismatched
types, missing required fields, wrong HTTP status codes, forbidden extra fields
leaking into responses. This environment turns that real-world task into a
structured RL benchmark.

The agent receives a broken API spec and a list of violations. Each step, it
proposes one fix. It gets rewarded for each violation resolved and penalised
for introducing new ones.

---

## Action Space

```json
{
  "kind": "add_field | remove_field | change_type | change_status | no_op",
  "endpoint_index": 0,
  "location": "request_body | response_body | status_code",
  "field_name": "field_name_or_null",
  "new_value": "<type string | field spec dict | int status code | null>"
}
```

| `kind`          | `new_value` type | Description |
|-----------------|-----------------|-------------|
| `add_field`     | `{"type": "...", "required": true, "description": "..."}` | Add a missing field |
| `remove_field`  | `null` | Remove a forbidden field |
| `change_type`   | `"integer"` / `"string"` / `"boolean"` / `"number"` | Fix a field's type |
| `change_status` | `204` / `200` / `201` etc. | Fix the HTTP status code |
| `no_op`         | `null` | Do nothing (small implicit cost) |

---

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `task_name` | str | Active task: `easy`, `medium`, `hard` |
| `task_description` | str | Plain-English description of violations |
| `endpoints` | list | Current (partially fixed) endpoint specs |
| `violations` | list | Remaining violations with type + description |
| `violations_fixed_this_step` | int | How many the last action resolved |
| `violations_introduced_this_step` | int | How many the last action introduced |
| `total_violations_at_start` | int | Violation count at episode start |
| `step_count` | int | Steps taken so far |
| `max_steps` | int | Episode step budget |
| `last_action_error` | str\|null | Validation error if action was malformed |
| `reward` | float | Per-step reward |
| `done` | bool | Whether the episode has terminated |

---

## Tasks

### Easy (1 endpoint, 1 violation, max 5 steps)
A user registration endpoint is missing `created_at` (string) in its response.
Expected score for a capable agent: **1.0**

### Medium (3 endpoints, 3 violations, max 10 steps)
An e-commerce API has:
1. `GET /products/{id}` — `product_id` returned as `string` instead of `integer`
2. `POST /orders` — `quantity` accepted as `string` instead of `integer`
3. `DELETE /orders/{id}` — returns status `200` instead of `204`

Expected score for a capable agent: **1.0**

### Hard (4 endpoints, 6 violations, max 15 steps)
An auth + profile API has:
1. `POST /auth/login` — missing `refresh_token` in response
2. `POST /auth/login` — `expires_in` is `string` instead of `integer`
3. `GET /users/{id}/profile` — missing `created_at` in response
4. `GET /users/{id}/profile` — exposes forbidden `password_hash` field (must be removed)
5. `PATCH /users/{id}/profile` — returns status `500` instead of `200`
6. `PATCH /users/{id}/profile` — missing `updated_at` in response

Expected score for a capable agent: **0.7–1.0** (frontier models)

---

## Reward Function

| Event | Reward |
|-------|--------|
| Fix a violation | `+0.2 × severity` |
| Introduce a violation | `−0.15 × severity` |
| Malformed action | `−0.05` |
| Solve all violations | `+0.5` bonus |

Severity weights: `missing_field=1.0`, `wrong_type=0.9`, `wrong_status=0.8`, `extra_field=0.7`

Final episode score is computed by `grade_episode()` → float in `[0.0, 1.0]`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Reset environment. Body: `{"task_name": "easy\|medium\|hard"}` |
| `POST` | `/step`  | Apply one action. Body: `{"action": {...}}` |
| `GET`  | `/state` | Full internal state |
| `GET`  | `/score` | Final episode score |
| `GET`  | `/tasks` | List all available tasks |
| `GET`  | `/health`| Health check |
| `GET`  | `/schema`| JSON schemas for action + observation |

---

## Setup & Usage

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd api-contract-debugger

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Run locally

```bash
# Start the server
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload
```

The server will be available at `http://localhost:7860`

### Run with Docker

```bash
docker build -t api-contract-debugger .
docker run -p 7860:7860 api-contract-debugger
```

### Run tests

```bash
# Run entire test suite (56 tests)
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=server
```

### Run the baseline agent

The baseline agent uses an LLM (via OpenAI client) to propose fixes.

**Required environment variables** (must be set):
```bash
export HF_TOKEN="your_huggingface_api_token"     # Get from huggingface.co/settings/tokens
export ENV_BASE_URL="http://localhost:7860"      # Environment server URL
export TASK_NAME="all"                           # "easy", "medium", "hard", or "all"
```

**Optional environment variables** (have defaults):
```bash
export API_BASE_URL="https://router.huggingface.co/v1"      # LLM endpoint
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"               # Model identifier
export LOCAL_IMAGE_NAME="optional_docker_image"             # For docker image initialization
```

Then run the agent:
```bash
python inference.py
```

**Example output:**
```
[START] task=easy env=api_contract_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action={"kind":"add_field",...} reward=0.70 done=true error=null
[END] success=true steps=1 score=1.000 rewards=0.70
```

### Test individual endpoints

```bash
# Health check
curl http://localhost:7860/health

# List available tasks
curl http://localhost:7860/tasks

# Reset to a task
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_name":"easy"}'

# Apply an action
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "kind": "add_field",
      "endpoint_index": 0,
      "location": "response_body",
      "field_name": "created_at",
      "new_value": {"type": "string", "description": "ISO-8601 timestamp"}
    }
  }'

# Get final score
curl http://localhost:7860/score
```

---

## Baseline Scores

| Task | Model | Score | Steps Used |
|------|-------|-------|-----------|
| easy | Qwen2.5-72B-Instruct | 1.000 | 1 |
| medium | Qwen2.5-72B-Instruct | 1.000 | 3 |
| hard | Qwen2.5-72B-Instruct | ~0.85 | 12 |

---

## Project Structure

```
api-contract-debugger/
├── server/
│   ├── __init__.py
│   ├── app.py          # FastAPI app, route registration
│   ├── environment.py  # OpenEnv Environment subclass
│   ├── models.py       # Pydantic Action / Observation / State
│   ├── graders.py      # Violation detection + reward shaping
│   └── fixtures.py     # Task definitions (broken + golden specs)
├── tests/
│   └── test_env.py     # 56 unit tests covering all components
├── inference.py        # Baseline LLM-powered agent
├── openenv.yaml        # OpenEnv metadata
├── pyproject.toml      # Package configuration
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container image configuration
└── RL_ARCHITECTURE.md  # Complete RL framework documentation
```

---

## Documentation

### RL_ARCHITECTURE.md
Comprehensive guide to the reinforcement learning implementation:
- **Agent** — How external AI systems interact with the environment via HTTP API
- **Environment** — Core `APIContractDebuggerEnv` class and episode lifecycle
- **State** — Observation space and full internal state representation
- **Action** — All 5 action types with validation rules and examples
- **Reward & Scoring** — Dense per-step rewards and episode grading formula
- **Complete example episode transcript** with JSON payloads
- **Python agent pseudocode** for custom implementations

---
