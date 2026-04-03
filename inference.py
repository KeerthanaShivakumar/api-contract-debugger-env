"""
Baseline Inference Script — API Contract Debugger
===================================================
Runs a GPT model against all three tasks and emits the required
[START] / [STEP] / [END] log format.

Environment variables:
    API_BASE_URL   LLM endpoint  (default: https://router.huggingface.co/v1)
    MODEL_NAME     Model ID      (default: Qwen/Qwen2.5-72B-Instruct)
    HF_TOKEN       API key
    ENV_BASE_URL   Running env   (default: http://localhost:7860)
    TASK_NAME      One task or "all"  (default: all)
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "hf_placeholder")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860").rstrip("/")
TASK_NAME    = os.getenv("TASK_NAME", "all")

TEMPERATURE  = 0.0
MAX_TOKENS   = 512
BENCHMARK    = "api_contract_debugger"

TASKS = ["easy", "medium", "hard"]

# ---------------------------------------------------------------------------
# Logging helpers (required stdout format)
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Environment HTTP client
# ---------------------------------------------------------------------------

def env_reset(task_name: str) -> Dict[str, Any]:
    r = requests.post(f"{ENV_BASE_URL}/reset", json={"task_name": task_name}, timeout=30)
    r.raise_for_status()
    return r.json()


def env_step(action_payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{ENV_BASE_URL}/step", json={"action": action_payload}, timeout=30)
    r.raise_for_status()
    return r.json()


def env_score() -> float:
    r = requests.get(f"{ENV_BASE_URL}/score", timeout=10)
    r.raise_for_status()
    return float(r.json()["score"])


# ---------------------------------------------------------------------------
# LLM agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert API contract debugger. You will be shown a broken API spec
and a list of violations. Your job is to propose ONE fix per turn.

You must respond with ONLY a valid JSON object matching this schema:
{
  "kind": "add_field" | "remove_field" | "change_type" | "change_status" | "no_op",
  "endpoint_index": <integer, 0-based>,
  "location": "request_body" | "response_body" | "status_code",
  "field_name": <string or null>,
  "new_value": <string | integer | object | null>
}

Rules:
- add_field:     new_value must be {"type": "<type>", "required": true/false, "description": "..."}
- change_type:   new_value must be a type string e.g. "integer", "string", "boolean", "number"
- change_status: new_value must be an integer HTTP status code; location must be "status_code"
- remove_field:  new_value must be null
- no_op:         use when no fix is needed; new_value must be null

Do NOT include any explanation — output ONLY the JSON object.
""").strip()


def build_user_prompt(obs: Dict[str, Any], step: int, history: List[str]) -> str:
    violations = obs.get("violations", [])
    endpoints  = obs.get("endpoints", [])
    history_block = "\n".join(history[-6:]) if history else "None"

    viol_text = json.dumps(violations, indent=2) if violations else "None — all fixed!"
    ep_text   = json.dumps(endpoints, indent=2)

    return textwrap.dedent(f"""
        Step {step} | Task: {obs.get('task_name')} | Violations remaining: {len(violations)}

        TASK DESCRIPTION:
        {obs.get('task_description', '')}

        CURRENT ENDPOINTS:
        {ep_text}

        REMAINING VIOLATIONS:
        {viol_text}

        PREVIOUS ACTIONS:
        {history_block}

        Propose ONE fix as a JSON object.
    """).strip()


def get_action(client: OpenAI, obs: Dict[str, Any], step: int, history: List[str]) -> Dict[str, Any]:
    """Call the LLM and parse a DebugAction payload."""
    prompt = build_user_prompt(obs, step, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        text = (completion.choices[0].message.content or "").strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return {"kind": "no_op", "endpoint_index": 0, "location": "response_body",
                "field_name": None, "new_value": None}


# ---------------------------------------------------------------------------
# Single episode runner
# ---------------------------------------------------------------------------

def run_episode(client: OpenAI, task_name: str) -> None:
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0

    try:
        obs = env_reset(task_name)
        history: List[str] = []
        max_steps = obs.get("max_steps", 15)

        for step in range(1, max_steps + 1):
            if obs.get("done"):
                break

            action_payload = get_action(client, obs, step, history)
            action_str = json.dumps(action_payload, separators=(",", ":"))

            obs = env_step(action_payload)

            reward = float(obs.get("reward") or 0.0)
            done   = bool(obs.get("done", False))
            error  = obs.get("last_action_error")

            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            history.append(
                f"Step {step}: {action_str} → reward={reward:+.2f} "
                f"fixed={obs.get('violations_fixed_this_step', 0)} "
                f"remaining={len(obs.get('violations', []))}"
            )

            if done:
                break

        score = env_score()
        success = score >= 0.8

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    tasks_to_run = TASKS if TASK_NAME == "all" else [TASK_NAME]
    for task in tasks_to_run:
        run_episode(client, task)


if __name__ == "__main__":
    main()
