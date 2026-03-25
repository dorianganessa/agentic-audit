"""Pydantic models for the YAML rule schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator

ConditionOperator = Literal[
    "eq", "ne", "contains", "not_contains", "matches", "in", "gt", "gte", "lt", "lte", "exists",
]


class Condition(BaseModel):
    """A single field-level condition."""

    field: str | None = None
    op: ConditionOperator | None = None
    value: Any = None

    # Shorthand operators — set automatically during parsing
    eq: Any = None
    ne: Any = None
    contains: str | None = None
    not_contains: str | None = None
    matches: str | None = None

    # Combinators
    all: list[Condition] | None = None  # AND
    any: list[Condition] | None = None  # OR
    not_: Condition | None = None  # NOT (aliased from 'not' in YAML)

    model_config = {"populate_by_name": True}

    @field_validator("not_", mode="before")
    @classmethod
    def _parse_not(cls, v: Any, info: Any) -> Any:
        return v

    def is_combinator(self) -> bool:
        return self.all is not None or self.any is not None or self.not_ is not None

    def resolve_op_and_value(self) -> tuple[ConditionOperator, Any]:
        """Resolve shorthand operators to (op, value) tuple."""
        if self.op is not None:
            return self.op, self.value
        if self.eq is not None:
            return "eq", self.eq
        if self.ne is not None:
            return "ne", self.ne
        if self.contains is not None:
            return "contains", self.contains
        if self.not_contains is not None:
            return "not_contains", self.not_contains
        if self.matches is not None:
            return "matches", self.matches
        return "exists", True


class Effects(BaseModel):
    """What happens when a rule matches."""

    risk_level: str | None = None
    tags: list[str] = []
    block: bool = False
    frameworks: dict[str, str] = {}


class Rule(BaseModel):
    """A single evaluation rule."""

    id: str
    name: str
    description: str = ""
    severity: str = "low"  # informational, low, medium, high, critical
    category: str = "general"  # security, privacy, compliance, operational
    enabled: bool = True
    tags: list[str] = []

    match: Condition
    effects: Effects

    # Source tracking
    source: str = "builtin"  # builtin, custom, plugin


class RuleFile(BaseModel):
    """Top-level structure of a YAML rule file."""

    rules: list[Rule]
