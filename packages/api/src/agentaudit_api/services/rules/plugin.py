"""Python plugin system for custom rules.

Allows defining rules as decorated Python functions for logic too
complex to express in YAML (e.g., cross-field correlations, external
lookups, stateful detection).

Usage::

    from agentaudit_api.services.rules.plugin import rule, PluginResult

    @rule(
        id="custom-secret-scan",
        name="Custom Secret Scanner",
        severity="critical",
        category="security",
        tags=["custom"],
    )
    def detect_custom_secrets(event: dict) -> PluginResult | None:
        command = (event.get("data") or {}).get("command", "")
        if "MY_INTERNAL_TOKEN" in command:
            return PluginResult(risk_level="critical", tags=["internal-token"])
        return None  # No match
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agentaudit_api.services.rules.schema import Condition, Effects, Rule

logger = logging.getLogger(__name__)

# Global registry of plugin functions
_plugin_registry: list[PluginRule] = []


@dataclass
class PluginResult:
    """Return value from a plugin rule function when the rule matches."""

    risk_level: str | None = None
    tags: list[str] = field(default_factory=list)
    block: bool = False
    frameworks: dict[str, str] = field(default_factory=dict)


@dataclass
class PluginRule:
    """A rule backed by a Python function."""

    id: str
    name: str
    description: str
    severity: str
    category: str
    tags: list[str]
    enabled: bool
    fn: Callable[[dict[str, Any]], PluginResult | None]


def rule(
    *,
    id: str,
    name: str,
    description: str = "",
    severity: str = "medium",
    category: str = "general",
    tags: list[str] | None = None,
    enabled: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorator to register a Python function as a rule.

    The decorated function receives an event dict and returns a
    ``PluginResult`` if the rule matches, or ``None`` if it doesn't.

    Args:
        id: Unique rule identifier.
        name: Human-readable name.
        description: What this rule detects.
        severity: Rule severity level.
        category: Rule category.
        tags: Tags applied when the rule matches.
        enabled: Whether the rule is active.
    """
    def decorator(fn: Callable[[dict[str, Any]], PluginResult | None]) -> Callable:
        plugin_rule = PluginRule(
            id=id,
            name=name,
            description=description,
            severity=severity,
            category=category,
            tags=tags or [],
            enabled=enabled,
            fn=fn,
        )
        _plugin_registry.append(plugin_rule)
        fn._plugin_rule = plugin_rule  # type: ignore[attr-defined]
        return fn

    return decorator


def get_registered_plugins() -> list[PluginRule]:
    """Return all registered plugin rules."""
    return list(_plugin_registry)


def clear_registry() -> None:
    """Clear all registered plugins (useful for testing)."""
    _plugin_registry.clear()


def load_plugin_file(path: Path) -> list[PluginRule]:
    """Load plugin rules from a Python file by importing it.

    The file should use the ``@rule`` decorator to register functions.

    Args:
        path: Path to a .py file.

    Returns:
        List of PluginRule objects defined in the file.
    """
    before = set(id(r) for r in _plugin_registry)

    module_name = f"agentaudit_plugin_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        logger.warning("Cannot load plugin from %s", path)
        return []

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("Failed to load plugin %s", path)
        sys.modules.pop(module_name, None)
        return []

    new_rules = [r for r in _plugin_registry if id(r) not in before]
    logger.debug("Loaded %d plugin rules from %s", len(new_rules), path.name)
    return new_rules


def load_plugin_directory(directory: Path) -> list[PluginRule]:
    """Load all .py plugin files from a directory.

    Args:
        directory: Path to scan for .py plugin files.

    Returns:
        All PluginRule objects found.
    """
    rules: list[PluginRule] = []

    if not directory.exists():
        return rules

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            rules.extend(load_plugin_file(path))
        except Exception:
            logger.exception("Failed to load plugin file %s", path)

    return rules
