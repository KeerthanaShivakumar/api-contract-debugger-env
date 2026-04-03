"""
Typed Pydantic models for the API Contract Debugger environment.

The environment gives an agent a broken OpenAPI-style spec and asks it to
fix contract violations by proposing targeted field-level corrections.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class FieldType(str, Enum):
    """Supported JSON Schema primitive types."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ActionKind(str, Enum):
    """What kind of fix the agent is proposing."""
    ADD_FIELD = "add_field"          # Add a missing required field
    REMOVE_FIELD = "remove_field"    # Remove a forbidden/extra field
    CHANGE_TYPE = "change_type"      # Fix a field's type
    CHANGE_STATUS = "change_status"  # Fix an HTTP status code
    NO_OP = "no_op"                  # Agent explicitly passes this step


# ---------------------------------------------------------------------------
# API Spec domain models (not OpenEnv base classes)
# ---------------------------------------------------------------------------

class FieldSpec(dict):
    """A JSON Schema-like field definition. Stored as plain dict for flexibility."""
    pass


class EndpointSpec(dict):
    """A single endpoint definition: method, path, request_body, response."""
    pass


# ---------------------------------------------------------------------------
# OpenEnv Action
# ---------------------------------------------------------------------------

class DebugAction(Action):
    """
    A single fix proposed by the agent.

    The agent targets one endpoint + one field and proposes exactly one change.
    """

    kind: ActionKind = Field(
        ...,
        description="The type of fix being applied",
    )
    endpoint_index: int = Field(
        ...,
        ge=0,
        description="0-based index into the endpoint list",
    )
    location: str = Field(
        ...,
        description=(
            "Where in the endpoint to apply the fix. "
            "One of: 'request_body', 'response_body', 'status_code'"
        ),
    )
    field_name: Optional[str] = Field(
        default=None,
        description="Field name to add/remove/change (null for status_code fixes)",
    )
    new_value: Optional[Any] = Field(
        default=None,
        description=(
            "The corrected value. "
            "For CHANGE_TYPE: a FieldType string. "
            "For ADD_FIELD: a dict with 'type' (and optional 'description'). "
            "For CHANGE_STATUS: an integer HTTP status code. "
            "For REMOVE_FIELD / NO_OP: null."
        ),
    )


# ---------------------------------------------------------------------------
# OpenEnv Observation
# ---------------------------------------------------------------------------

class Violation(dict):
    """
    Describes a single detected contract violation.

    Keys: endpoint_index, location, field_name, violation_type, description
    """
    pass


class DebugObservation(Observation):
    """
    What the agent sees after each reset() / step().
    """

    task_name: str = Field(
        ...,
        description="Which task is currently active (easy / medium / hard)",
    )
    task_description: str = Field(
        ...,
        description="Human-readable description of the task objective",
    )
    endpoints: List[Dict[str, Any]] = Field(
        ...,
        description="Current (potentially partially-fixed) endpoint specs",
    )
    violations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of detected violations still present in the spec",
    )
    violations_fixed_this_step: int = Field(
        default=0,
        description="How many violations the last action resolved",
    )
    violations_introduced_this_step: int = Field(
        default=0,
        description="How many new violations the last action introduced",
    )
    total_violations_at_start: int = Field(
        ...,
        description="Number of violations at episode start (for progress tracking)",
    )
    step_count: int = Field(
        default=0,
        description="Steps taken so far in this episode",
    )
    max_steps: int = Field(
        default=10,
        description="Maximum steps allowed per episode",
    )
    last_action_error: Optional[str] = Field(
        default=None,
        description="Error message if the last action was malformed / out-of-range",
    )


# ---------------------------------------------------------------------------
# OpenEnv State
# ---------------------------------------------------------------------------

class DebugState(State):
    """
    Full internal state of the environment (not exposed to the agent by default).
    """

    task_name: str = Field(default="")
    original_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    current_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    golden_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    total_violations_at_start: int = Field(default=0)
    max_steps: int = Field(default=10)
