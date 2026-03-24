"""Rule evaluation engine."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from agentaudit_api.services.rules.schema import Condition, Effects, Rule

if TYPE_CHECKING:
    from agentaudit_api.services.rules.plugin import PluginRule

logger = logging.getLogger(__name__)


@dataclass
class RuleMatch:
    """Result of a rule matching an event."""

    rule_id: str
    rule_name: str
    effects: Effects
    severity: str
    category: str
    tags: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Aggregated result of evaluating all rules against an event."""

    risk_level: str = "low"
    tags: list[str] = field(default_factory=list)
    matched_rules: list[RuleMatch] = field(default_factory=list)
    block: bool = False
    frameworks: dict[str, str] = field(default_factory=dict)


_RISK_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class RuleEngine:
    """Evaluate events against a set of YAML and Python plugin rules."""

    def __init__(
        self,
        rules: list[Rule] | None = None,
        plugins: list[PluginRule] | None = None,
    ) -> None:
        self._rules: list[Rule] = rules or []
        self._plugins: list[PluginRule] = plugins or []

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    @property
    def plugins(self) -> list[PluginRule]:
        return list(self._plugins)

    def add_rules(self, rules: list[Rule]) -> None:
        self._rules.extend(rules)

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_plugin(self, plugin: PluginRule) -> None:
        self._plugins.append(plugin)

    def add_plugins(self, plugins: list[PluginRule]) -> None:
        self._plugins.extend(plugins)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules) + len(self._plugins)
        self._rules = [r for r in self._rules if r.id != rule_id]
        self._plugins = [p for p in self._plugins if p.id != rule_id]
        after = len(self._rules) + len(self._plugins)
        return after < before

    def evaluate(self, event: dict[str, Any]) -> EvaluationResult:
        """Evaluate all enabled YAML rules and Python plugins against an event.

        Args:
            event: Dict with keys: action, agent_id, data, context,
                   pii_detected, pii_fields, reasoning.

        Returns:
            Aggregated result with highest risk level and all matched rules.
        """
        result = EvaluationResult()

        # Evaluate YAML rules
        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                if _evaluate_condition(rule.match, event):
                    match = RuleMatch(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        effects=rule.effects,
                        severity=rule.severity,
                        category=rule.category,
                        tags=rule.tags,
                    )
                    result.matched_rules.append(match)
                    _apply_effects(result, rule.effects, rule.tags)
            except Exception:
                logger.exception("Error evaluating rule '%s'", rule.id)

        # Evaluate Python plugin rules
        for plugin in self._plugins:
            if not plugin.enabled:
                continue

            try:
                plugin_result = plugin.fn(event)
                if plugin_result is not None:
                    effects = Effects(
                        risk_level=plugin_result.risk_level,
                        tags=plugin_result.tags,
                        block=plugin_result.block,
                        frameworks=plugin_result.frameworks,
                    )
                    match = RuleMatch(
                        rule_id=plugin.id,
                        rule_name=plugin.name,
                        effects=effects,
                        severity=plugin.severity,
                        category=plugin.category,
                        tags=plugin.tags,
                    )
                    result.matched_rules.append(match)
                    _apply_effects(result, effects, plugin.tags)
            except Exception:
                logger.exception("Error evaluating plugin rule '%s'", plugin.id)

        return result


def _apply_effects(result: EvaluationResult, effects: Effects, rule_tags: list[str]) -> None:
    """Merge a rule's effects into the aggregated result."""
    if effects.risk_level:
        new_order = _RISK_ORDER.get(effects.risk_level, 0)
        current_order = _RISK_ORDER.get(result.risk_level, 0)
        if new_order > current_order:
            result.risk_level = effects.risk_level

    result.tags.extend(effects.tags)
    result.tags.extend(rule_tags)

    if effects.block:
        result.block = True

    result.frameworks.update(effects.frameworks)


def _evaluate_condition(condition: Condition, event: dict[str, Any]) -> bool:
    """Recursively evaluate a condition tree against an event."""
    # Combinator: all (AND)
    if condition.all is not None:
        return all(_evaluate_condition(c, event) for c in condition.all)

    # Combinator: any (OR)
    if condition.any is not None:
        return any(_evaluate_condition(c, event) for c in condition.any)

    # Combinator: not
    if condition.not_ is not None:
        return not _evaluate_condition(condition.not_, event)

    # Leaf condition: field + operator
    if condition.field is None:
        return False

    field_value = _resolve_field(condition.field, event)
    op, expected = condition.resolve_op_and_value()
    return _apply_operator(op, field_value, expected)


def _resolve_field(field_path: str, event: dict[str, Any]) -> Any:
    """Resolve a dotted field path against the event dict.

    Special handling:
    - 'data' without subpath → flattened string of all data values
    - 'context' without subpath → flattened string of all context values
    - 'data.command' → event["data"]["command"]
    """
    parts = field_path.split(".", 1)
    top = parts[0]

    if top not in event:
        return None

    value = event[top]

    if len(parts) == 1:
        # For dict fields without a subpath, flatten to string for pattern matching
        if isinstance(value, dict):
            return _flatten_to_str(value)
        return value

    # Dotted access into nested dicts
    subpath = parts[1]
    if isinstance(value, dict):
        return _resolve_nested(value, subpath)
    return None


def _resolve_nested(data: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path into a nested dict."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _flatten_to_str(data: object) -> str:
    """Recursively flatten a dict/list to a single string for pattern matching."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_flatten_to_str(v) for v in data.values())
    if isinstance(data, list):
        return " ".join(_flatten_to_str(v) for v in data)
    return str(data) if data is not None else ""


def _apply_operator(op: str, field_value: Any, expected: Any) -> bool:
    """Apply a comparison operator."""
    if op == "exists":
        return (field_value is not None and field_value != "") == bool(expected)

    if op == "eq":
        return field_value == expected

    if op == "ne":
        return field_value != expected

    if op == "contains":
        if field_value is None:
            return False
        return str(expected).lower() in str(field_value).lower()

    if op == "not_contains":
        if field_value is None:
            return True
        return str(expected).lower() not in str(field_value).lower()

    if op == "matches":
        if field_value is None:
            return False
        return bool(re.search(str(expected), str(field_value)))

    if op == "in":
        if not isinstance(expected, list):
            return False
        return field_value in expected

    if op in ("gt", "gte", "lt", "lte"):
        try:
            fv = float(field_value) if field_value is not None else 0
            ev = float(expected)
        except (TypeError, ValueError):
            return False
        if op == "gt":
            return fv > ev
        if op == "gte":
            return fv >= ev
        if op == "lt":
            return fv < ev
        return fv <= ev

    return False
