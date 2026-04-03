# Complete Rerun Guide - After All Changes

## Overview of Changes Made

1. ✅ **inference.py** — Fixed environment variable configuration for strict compliance
2. ✅ **RL_ARCHITECTURE.md** — Created full RL documentation 

---

## Step-by-Step Rerun Instructions

### Phase 1: Verify Prerequisites

```bash
# Check Python version (requires 3.10+)
python3 --version

# Check pip
pip3 --version

# Verify you're in the project directory
cd /Users/keerthanashivakumar/Desktop/Scaler\ x\ Meta\ OpenEnv\ hackathon/api-contract-debugger
pwd
```

### Phase 2: Clean Install & Dependency Setup

```bash
# 1. Remove old virtual environment (OPTIONAL - only if you want a fresh install)
rm -rf .venv

# 2. Create fresh virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Upgrade pip
pip install --upgrade pip

# 5. Install all dependencies from requirements.txt
pip install -r requirements.txt

# 6. Verify installations
pip list | grep -E "fastapi|uvicorn|pydantic|openai|requests"
```

**Expected output** (all should be present):
```
fastapi          0.135.3
uvicorn          0.42.0
pydantic         2.12.5
openai           2.30.0
requests         2.33.1
```

---

### Phase 3: Start the Server

**Terminal 1: Start the Uvicorn server**

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Start the server (reload mode for development)
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:7860 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXX] using WatchFiles
```

**Verify server is running:**
```bash
# Terminal 2: Quick health check
curl http://localhost:7860/health
# Should return: {"status":"ok"} or similar
```

---

### Phase 4: Run Tests (IMPORTANT - Verify Everything Works)

**Terminal 2: Run the test suite**

```bash
# Activate venv in new terminal
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Or run specific test file
pytest tests/test_env.py -v

# Run with coverage
pytest tests/ -v --cov=server
```

**Expected output:**
```
test_env.py::test_reset PASSED
test_env.py::test_step_add_field PASSED
test_env.py::test_violations_detection PASSED
... (all 56 tests should PASS)
```

---

### Phase 5: Run the Baseline Agent (inference.py)

**⚠️ IMPORTANT: New Environment Variable Requirements**

After the compliance fixes, `inference.py` now requires these environment variables:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `HF_TOKEN` or `API_KEY` | ✅ YES | None | API key for LLM |
| `ENV_BASE_URL` | ✅ YES | None | Environment server URL |
| `TASK_NAME` | ✅ YES | None | Task: "easy", "medium", "hard", or "all" |
| `API_BASE_URL` | ❌ NO | https://router.huggingface.co/v1 | LLM endpoint |
| `MODEL_NAME` | ❌ NO | Qwen/Qwen2.5-72B-Instruct | Model ID |

**Terminal 3: Run the agent against all tasks**

```bash
# Activate venv
source .venv/bin/activate

# Set required environment variables
export HF_TOKEN="your_huggingface_token_here"  # Get from https://huggingface.co/settings/tokens
export ENV_BASE_URL="http://localhost:7860"
export TASK_NAME="all"              # "easy", "medium", "hard", or "all"

# Run the agent
python inference.py
```

**Expected output (stdout format):**
```
[START] task=easy env=api_contract_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action={"kind":"add_field",...} reward=0.70 done=true error=null
[END] success=true steps=1 score=1.000 rewards=0.70

[START] task=medium env=api_contract_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action={"kind":"change_type",...} reward=0.18 done=false error=null
[STEP] step=2 action={"kind":"change_type",...} reward=0.18 done=false error=null
[STEP] step=3 action={"kind":"change_status",...} reward=0.16 done=true error=null
[END] success=true steps=3 score=1.000 rewards=0.18,0.18,0.16

[START] task=hard env=api_contract_debugger model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action={...} reward=0.20 done=false error=null
...
[END] success=true steps=N score=X.XXX rewards=...
```

---

### Phase 6: Test Individual Endpoints Manually

**Terminal 4: Verify API endpoints work**

```bash
# 1. Check available tasks
curl http://localhost:7860/tasks | json_pp

# 2. Reset to easy task
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_name":"easy"}' | json_pp

# 3. Apply an action
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "kind": "add_field",
      "endpoint_index": 0,
      "location": "response_body",
      "field_name": "created_at",
      "new_value": {"type": "string", "description": "Creation timestamp"}
    }
  }' | json_pp

# 4. Get current state
curl http://localhost:7860/state | json_pp

# 5. Get final score
curl http://localhost:7860/score | json_pp
```

---

## Complete Example: Run One Task Step-by-Step

### Option A: Using curl (Manual Testing)

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

# Terminal 2: Run through an episode manually
# 1. Reset
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_name":"easy"}'

# 2. Inspect the observation to see violations
# → Look at the violations field to understand the problem

# 3. Apply fix
curl -X POST http://localhost:7860/step -H "Content-Type: application/json" \
  -d '{"action":{"kind":"add_field","endpoint_index":0,"location":"response_body","field_name":"created_at","new_value":{"type":"string"}}}'

# 4. Check if done
curl http://localhost:7860/state | grep -i "done"

# 5. Get score
curl http://localhost:7860/score
```

### Option B: Using Python Script

```bash
# Terminal 1: Start server
source .venv/bin/activate
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

# Terminal 2: Run Python test
python3 << 'EOF'
import requests
import json

BASE_URL = "http://localhost:7860"

# Reset
obs = requests.post(f"{BASE_URL}/reset", json={"task_name": "easy"}).json()
print(f"Violations at start: {len(obs['violations'])}")
print(f"Max steps: {obs['max_steps']}")

# Step 1: Add the missing field
action = {
    "kind": "add_field",
    "endpoint_index": 0,
    "location": "response_body",
    "field_name": "created_at",
    "new_value": {"type": "string", "description": "ISO-8601 timestamp"}
}

obs = requests.post(f"{BASE_URL}/step", json={"action": action}).json()
print(f"\nAfter action:")
print(f"Reward: {obs['reward']}")
print(f"Done: {obs['done']}")
print(f"Violations remaining: {len(obs['violations'])}")

# Get final score
score = requests.get(f"{BASE_URL}/score").json()
print(f"\nFinal score: {score['score']}")
EOF
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'server'"
**Solution:**
```bash
# Make sure you're in the project root
pwd  # should end with: api-contract-debugger

# Ensure venv is activated
source .venv/bin/activate

# Reinstall in editable mode
pip install -e .
```

### Issue: "API key must be provided via HF_TOKEN or API_KEY" (when running inference.py)
**Solution:**
```bash
# The new version requires explicit environment variables
export HF_TOKEN="hf_xxxxxxxxxxxx"  # Get from huggingface.co/settings/tokens
export ENV_BASE_URL="http://localhost:7860"
export TASK_NAME="easy"  # or "medium", "hard", "all"
python inference.py
```

### Issue: "ENV_BASE_URL environment variable must be set"
**Solution:**
```bash
# This is now required (no default)
export ENV_BASE_URL="http://localhost:7860"
python inference.py
```

### Issue: Port 7860 already in use
**Solution:**
```bash
# Kill existing process
lsof -i :7860  # Find process ID
kill -9 <PID>

# Or use different port
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Issue: Tests failing
**Solution:**
```bash
# Ensure server is NOT running (tests run their own environment)
pytest tests/ -v -s  # -s for print statements

# If still failing, check if port 7860 is free
lsof -i :7860
```

---

## Quick Reference: Full Clean Rerun

```bash
#!/bin/bash
# Copy-paste this to do a complete clean rerun

# Navigate to project
cd /Users/keerthanashivakumar/Desktop/Scaler\ x\ Meta\ OpenEnv\ hackathon/api-contract-debugger

# Clean install
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Terminal 1: Start server
uvicorn server.app:app --host 0.0.0.0 --port 7860 &

# Wait for server to start
sleep 3

# Terminal 2: Run tests
pytest tests/ -v

# Terminal 3: Run agent
export HF_TOKEN="your_token"
export ENV_BASE_URL="http://localhost:7860"
export TASK_NAME="all"
python inference.py

# Kill server when done
pkill -f uvicorn
```

---

## What to Verify

After complete rerun, verify:

✅ Server starts without errors
✅ `/health` endpoint returns status
✅ All 56 tests pass
✅ `inference.py` requires environment variables (doesn't run without them)
✅ Agent runs and produces [START]/[STEP]/[END] logs
✅ RL_ARCHITECTURE.md exists in repo root

---

## File Structure After Rerun

```
api-contract-debugger/
├── .venv/                    # Virtual environment (after venv creation)
├── server/
│   ├── app.py
│   ├── environment.py
│   ├── models.py
│   ├── graders.py
│   ├── fixtures.py
│   └── __pycache__/
├── tests/
│   └── test_env.py
├── inference.py              # ✅ NOW COMPLIANT (env vars required)
├── RL_ARCHITECTURE.md        # ✅ NEW: Full RL documentation
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── README.md
```

---
