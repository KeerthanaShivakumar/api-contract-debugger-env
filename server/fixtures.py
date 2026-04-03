"""
Task fixtures for the API Contract Debugger environment.

Each task is a dict with:
  - name: str
  - description: str
  - broken_endpoints: list[dict]   — what the agent starts with
  - golden_endpoints: list[dict]   — the correct spec the grader checks against
  - max_steps: int

Endpoint schema:
  {
    "method": str,
    "path": str,
    "status_code": int,
    "request_body": {
        "<field>": {"type": str, "required": bool, "description": str}
    },
    "response_body": {
        "<field>": {"type": str, "required": bool, "description": str}
    }
  }
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Task 1 — EASY
# Single endpoint. One missing required field in the response.
# ---------------------------------------------------------------------------

_TASK1_GOLDEN: List[Dict[str, Any]] = [
    {
        "method": "POST",
        "path": "/users/register",
        "status_code": 201,
        "request_body": {
            "username": {"type": "string", "required": True,  "description": "Desired username"},
            "email":    {"type": "string", "required": True,  "description": "User email address"},
            "password": {"type": "string", "required": True,  "description": "Plaintext password"},
        },
        "response_body": {
            "user_id":    {"type": "integer", "required": True,  "description": "Created user ID"},
            "username":   {"type": "string",  "required": True,  "description": "Confirmed username"},
            "created_at": {"type": "string",  "required": True,  "description": "ISO-8601 timestamp"},
        },
    }
]

# Break it: remove "created_at" from response
_TASK1_BROKEN: List[Dict[str, Any]] = copy.deepcopy(_TASK1_GOLDEN)
del _TASK1_BROKEN[0]["response_body"]["created_at"]

TASK_EASY: Dict[str, Any] = {
    "name": "easy",
    "description": (
        "A user registration endpoint is missing a required field in its response. "
        "The response should include user_id (integer), username (string), and "
        "created_at (string). Find and add the missing field."
    ),
    "broken_endpoints": _TASK1_BROKEN,
    "golden_endpoints": _TASK1_GOLDEN,
    "max_steps": 5,
}


# ---------------------------------------------------------------------------
# Task 2 — MEDIUM
# Three endpoints. Type mismatches and a wrong status code.
# ---------------------------------------------------------------------------

_TASK2_GOLDEN: List[Dict[str, Any]] = [
    {
        "method": "GET",
        "path": "/products/{id}",
        "status_code": 200,
        "request_body": {},
        "response_body": {
            "product_id": {"type": "integer", "required": True,  "description": "Product ID"},
            "name":        {"type": "string",  "required": True,  "description": "Product name"},
            "price":       {"type": "number",  "required": True,  "description": "Price in USD"},
            "in_stock":    {"type": "boolean", "required": True,  "description": "Availability"},
        },
    },
    {
        "method": "POST",
        "path": "/orders",
        "status_code": 201,
        "request_body": {
            "product_id": {"type": "integer", "required": True,  "description": "Product to order"},
            "quantity":   {"type": "integer", "required": True,  "description": "Number of units"},
            "customer_id":{"type": "integer", "required": True,  "description": "Buyer ID"},
        },
        "response_body": {
            "order_id":   {"type": "integer", "required": True,  "description": "Created order ID"},
            "total_price":{"type": "number",  "required": True,  "description": "Total cost"},
            "status":     {"type": "string",  "required": True,  "description": "Order status"},
        },
    },
    {
        "method": "DELETE",
        "path": "/orders/{id}",
        "status_code": 204,
        "request_body": {},
        "response_body": {},
    },
]

# Break it:
# 1. product_id type: integer → string   (GET /products/{id} response)
# 2. quantity type:   integer → string   (POST /orders request)
# 3. DELETE status_code: 204 → 200
_TASK2_BROKEN: List[Dict[str, Any]] = copy.deepcopy(_TASK2_GOLDEN)
_TASK2_BROKEN[0]["response_body"]["product_id"]["type"] = "string"   # violation 1
_TASK2_BROKEN[1]["request_body"]["quantity"]["type"] = "string"       # violation 2
_TASK2_BROKEN[2]["status_code"] = 200                                  # violation 3

TASK_MEDIUM: Dict[str, Any] = {
    "name": "medium",
    "description": (
        "An e-commerce API has three endpoints with contract violations: "
        "(1) GET /products/{id} returns product_id as string instead of integer, "
        "(2) POST /orders accepts quantity as string instead of integer, "
        "(3) DELETE /orders/{id} returns status 200 instead of 204. "
        "Fix all three violations."
    ),
    "broken_endpoints": _TASK2_BROKEN,
    "golden_endpoints": _TASK2_GOLDEN,
    "max_steps": 10,
}


# ---------------------------------------------------------------------------
# Task 3 — HARD
# Multi-endpoint API. Missing required fields, type errors, wrong status code,
# AND a forbidden extra field that must be removed.
# ---------------------------------------------------------------------------

_TASK3_GOLDEN: List[Dict[str, Any]] = [
    {
        "method": "POST",
        "path": "/auth/login",
        "status_code": 200,
        "request_body": {
            "email":    {"type": "string", "required": True,  "description": "User email"},
            "password": {"type": "string", "required": True,  "description": "User password"},
        },
        "response_body": {
            "access_token":  {"type": "string",  "required": True,  "description": "JWT token"},
            "refresh_token": {"type": "string",  "required": True,  "description": "Refresh token"},
            "expires_in":    {"type": "integer", "required": True,  "description": "TTL in seconds"},
        },
    },
    {
        "method": "GET",
        "path": "/users/{id}/profile",
        "status_code": 200,
        "request_body": {},
        "response_body": {
            "user_id":    {"type": "integer", "required": True,  "description": "User ID"},
            "email":      {"type": "string",  "required": True,  "description": "User email"},
            "full_name":  {"type": "string",  "required": True,  "description": "Display name"},
            "role":       {"type": "string",  "required": True,  "description": "User role"},
            "created_at": {"type": "string",  "required": True,  "description": "ISO-8601 timestamp"},
        },
    },
    {
        "method": "PATCH",
        "path": "/users/{id}/profile",
        "status_code": 200,
        "request_body": {
            "full_name": {"type": "string", "required": False, "description": "Updated name"},
            "email":     {"type": "string", "required": False, "description": "Updated email"},
        },
        "response_body": {
            "user_id":   {"type": "integer", "required": True, "description": "User ID"},
            "full_name": {"type": "string",  "required": True, "description": "Updated name"},
            "email":     {"type": "string",  "required": True, "description": "Updated email"},
            "updated_at":{"type": "string",  "required": True, "description": "ISO-8601 timestamp"},
        },
    },
    {
        "method": "POST",
        "path": "/auth/refresh",
        "status_code": 200,
        "request_body": {
            "refresh_token": {"type": "string", "required": True, "description": "Refresh token"},
        },
        "response_body": {
            "access_token": {"type": "string",  "required": True, "description": "New JWT token"},
            "expires_in":   {"type": "integer", "required": True, "description": "TTL in seconds"},
        },
    },
]

_TASK3_BROKEN: List[Dict[str, Any]] = copy.deepcopy(_TASK3_GOLDEN)
# Violation 1: missing refresh_token in /auth/login response
del _TASK3_BROKEN[0]["response_body"]["refresh_token"]
# Violation 2: expires_in type integer → string in /auth/login response
_TASK3_BROKEN[0]["response_body"]["expires_in"]["type"] = "string"
# Violation 3: missing created_at in /users/{id}/profile response
del _TASK3_BROKEN[1]["response_body"]["created_at"]
# Violation 4: extra forbidden field "password_hash" in /users/{id}/profile response
_TASK3_BROKEN[1]["response_body"]["password_hash"] = {
    "type": "string", "required": False, "description": "Hashed password — MUST NOT be exposed"
}
# Violation 5: PATCH /users/{id}/profile status_code 200 → 500 (regression)
_TASK3_BROKEN[2]["status_code"] = 500
# Violation 6: missing updated_at in PATCH response
del _TASK3_BROKEN[2]["response_body"]["updated_at"]

TASK_HARD: Dict[str, Any] = {
    "name": "hard",
    "description": (
        "An authentication + profile API has 6 contract violations across 4 endpoints: "
        "(1) POST /auth/login is missing refresh_token in response, "
        "(2) POST /auth/login returns expires_in as string instead of integer, "
        "(3) GET /users/{id}/profile is missing created_at in response, "
        "(4) GET /users/{id}/profile exposes a forbidden password_hash field that must be removed, "
        "(5) PATCH /users/{id}/profile returns status 500 instead of 200, "
        "(6) PATCH /users/{id}/profile is missing updated_at in response. "
        "Fix all violations."
    ),
    "broken_endpoints": _TASK3_BROKEN,
    "golden_endpoints": _TASK3_GOLDEN,
    "max_steps": 15,
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TASKS: Dict[str, Dict[str, Any]] = {
    "easy":   TASK_EASY,
    "medium": TASK_MEDIUM,
    "hard":   TASK_HARD,
}
