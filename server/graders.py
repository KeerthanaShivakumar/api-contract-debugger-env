"""
Violation detection and graders for the API Contract Debugger environment.

detect_violations(current, golden) → list of violation dicts
grade_episode(current, golden) → float in [0.0, 1.0]
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------

def detect_violations(
    current_endpoints: List[Dict[str, Any]],
    golden_endpoints: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compare current spec against the golden spec and return all violations.

    Violation dict keys:
        endpoint_index  int   — index into endpoint list
        location        str   — "request_body" | "response_body" | "status_code"
        field_name      str|None
        violation_type  str   — "missing_field" | "extra_field" | "wrong_type" | "wrong_status"
        description     str   — human-readable explanation
        severity        float — weight used in scoring (0.0–1.0)
    """
    violations: List[Dict[str, Any]] = []

    for idx, (cur, gold) in enumerate(zip(current_endpoints, golden_endpoints)):
        # --- Status code ---
        if cur.get("status_code") != gold.get("status_code"):
            violations.append({
                "endpoint_index": idx,
                "location": "status_code",
                "field_name": None,
                "violation_type": "wrong_status",
                "description": (
                    f"{gold['method']} {gold['path']}: "
                    f"status_code is {cur.get('status_code')} "
                    f"but should be {gold.get('status_code')}"
                ),
                "severity": 0.8,
            })

        # --- Request body and response body ---
        for location in ("request_body", "response_body"):
            cur_body: Dict[str, Any] = cur.get(location, {})
            gold_body: Dict[str, Any] = gold.get(location, {})

            # Missing required fields
            for field, spec in gold_body.items():
                if field not in cur_body:
                    violations.append({
                        "endpoint_index": idx,
                        "location": location,
                        "field_name": field,
                        "violation_type": "missing_field",
                        "description": (
                            f"{gold['method']} {gold['path']} {location}: "
                            f"required field '{field}' ({spec['type']}) is missing"
                        ),
                        "severity": 1.0,
                    })
                else:
                    # Wrong type
                    cur_type = cur_body[field].get("type")
                    gold_type = spec.get("type")
                    if cur_type != gold_type:
                        violations.append({
                            "endpoint_index": idx,
                            "location": location,
                            "field_name": field,
                            "violation_type": "wrong_type",
                            "description": (
                                f"{gold['method']} {gold['path']} {location}: "
                                f"field '{field}' has type '{cur_type}' "
                                f"but should be '{gold_type}'"
                            ),
                            "severity": 0.9,
                        })

            # Extra (forbidden) fields — fields in current but not in golden
            for field in cur_body:
                if field not in gold_body:
                    violations.append({
                        "endpoint_index": idx,
                        "location": location,
                        "field_name": field,
                        "violation_type": "extra_field",
                        "description": (
                            f"{gold['method']} {gold['path']} {location}: "
                            f"field '{field}' is present but should not be in the contract"
                        ),
                        "severity": 0.7,
                    })

    return violations


# ---------------------------------------------------------------------------
# Grader
# ---------------------------------------------------------------------------

def grade_episode(
    current_endpoints: List[Dict[str, Any]],
    golden_endpoints: List[Dict[str, Any]],
    initial_violations: List[Dict[str, Any]],
) -> float:
    """
    Score the agent's performance at the END of an episode.

    Returns a float in [0.0, 1.0]:
        1.0  — all violations fixed, no new ones introduced
        0.0  — no improvement at all
        intermediate — partial credit weighted by severity

    Formula:
        score = (weighted_fixed - weighted_introduced) / total_initial_weight
        clamped to [0.0, 1.0]
    """
    remaining = detect_violations(current_endpoints, golden_endpoints)
    remaining_keys = _violation_keys(remaining)

    initial_keys = _violation_keys(initial_violations)

    # Violations that were present at start and are now gone = fixed
    fixed = [v for v in initial_violations if _vkey(v) not in remaining_keys]
    # Violations that are present now but weren't at start = newly introduced
    introduced = [v for v in remaining if _vkey(v) not in initial_keys]

    total_initial_weight = sum(v["severity"] for v in initial_violations)
    if total_initial_weight == 0:
        return 1.0  # spec was already clean

    weighted_fixed = sum(v["severity"] for v in fixed)
    weighted_introduced = sum(v["severity"] for v in introduced)

    raw = (weighted_fixed - weighted_introduced) / total_initial_weight
    return float(max(0.0, min(1.0, raw)))


def step_reward(
    prev_violations: List[Dict[str, Any]],
    new_violations: List[Dict[str, Any]],
    initial_violations: List[Dict[str, Any]],
    action_error: bool,
) -> float:
    """
    Dense per-step reward signal.

    +0.2  per violation resolved this step (weighted by severity)
    -0.15 per new violation introduced
    -0.05 for a malformed action (out-of-range index, bad field, etc.)
    """
    if action_error:
        return -0.05

    prev_keys = _violation_keys(prev_violations)
    new_keys = _violation_keys(new_violations)

    fixed_this_step = [v for v in prev_violations if _vkey(v) not in new_keys]
    introduced_this_step = [v for v in new_violations if _vkey(v) not in prev_keys]

    reward = 0.0
    for v in fixed_this_step:
        reward += 0.2 * v["severity"]
    for v in introduced_this_step:
        reward -= 0.15 * v["severity"]

    return round(reward, 4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vkey(v: Dict[str, Any]) -> tuple:
    return (
        v["endpoint_index"],
        v["location"],
        v.get("field_name"),
        v["violation_type"],
    )


def _violation_keys(violations: List[Dict[str, Any]]) -> set:
    return {_vkey(v) for v in violations}
