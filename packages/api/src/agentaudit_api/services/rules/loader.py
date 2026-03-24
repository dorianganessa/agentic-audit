"""Load rules from YAML files and Python plugins."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from agentaudit_api.services.rules.engine import RuleEngine
from agentaudit_api.services.rules.schema import Condition, Rule, RuleFile

logger = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).parent / "builtin"


def _preprocess_condition(data: Any) -> Any:
    """Recursively rename 'not' key to 'not_' for Pydantic compatibility."""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k == "not":
                result["not_"] = _preprocess_condition(v)
            else:
                result[k] = _preprocess_condition(v)
        return result
    if isinstance(data, list):
        return [_preprocess_condition(item) for item in data]
    return data


def load_yaml_file(path: Path) -> list[Rule]:
    """Load rules from a single YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        List of parsed Rule objects.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return []

    # Preprocess to handle 'not' → 'not_' renaming
    raw = _preprocess_condition(raw)

    rule_file = RuleFile.model_validate(raw)

    for rule in rule_file.rules:
        if rule.source == "builtin":
            rule.source = f"builtin:{path.stem}"

    return rule_file.rules


def load_yaml_string(content: str, source: str = "inline") -> list[Rule]:
    """Load rules from a YAML string.

    Args:
        content: YAML string.
        source: Source label for the rules.

    Returns:
        List of parsed Rule objects.
    """
    raw = yaml.safe_load(content)
    if raw is None:
        return []

    raw = _preprocess_condition(raw)
    rule_file = RuleFile.model_validate(raw)

    for rule in rule_file.rules:
        rule.source = source

    return rule_file.rules


def load_builtin_rules() -> list[Rule]:
    """Load all built-in YAML rules from the builtin/ directory."""
    rules: list[Rule] = []

    if not BUILTIN_DIR.exists():
        logger.warning("Built-in rules directory not found: %s", BUILTIN_DIR)
        return rules

    for path in sorted(BUILTIN_DIR.glob("*.yaml")):
        try:
            file_rules = load_yaml_file(path)
            rules.extend(file_rules)
            logger.debug("Loaded %d rules from %s", len(file_rules), path.name)
        except Exception:
            logger.exception("Failed to load rules from %s", path)

    return rules


def load_custom_rules(directory: Path) -> list[Rule]:
    """Load custom YAML rules from a user-specified directory."""
    rules: list[Rule] = []

    if not directory.exists():
        return rules

    for path in sorted(directory.glob("*.yaml")):
        try:
            file_rules = load_yaml_file(path)
            for rule in file_rules:
                rule.source = f"custom:{path.stem}"
            rules.extend(file_rules)
        except Exception:
            logger.exception("Failed to load custom rules from %s", path)

    return rules


def create_engine(
    *,
    include_builtin: bool = True,
    custom_dirs: list[Path] | None = None,
    plugin_dirs: list[Path] | None = None,
    extra_rules: list[Rule] | None = None,
) -> RuleEngine:
    """Create a RuleEngine with built-in, custom YAML, and Python plugin rules.

    Args:
        include_builtin: Whether to load built-in rules.
        custom_dirs: Directories to scan for custom YAML rules.
        plugin_dirs: Directories to scan for Python plugin files.
        extra_rules: Additional rules to include.

    Returns:
        A configured RuleEngine instance.
    """
    from agentaudit_api.services.rules.plugin import PluginRule, load_plugin_directory

    rules: list[Rule] = []
    plugins: list[PluginRule] = []

    if include_builtin:
        rules.extend(load_builtin_rules())

    if custom_dirs:
        for d in custom_dirs:
            rules.extend(load_custom_rules(d))

    if plugin_dirs:
        for d in plugin_dirs:
            plugins.extend(load_plugin_directory(d))

    if extra_rules:
        rules.extend(extra_rules)

    engine = RuleEngine(rules, plugins=plugins)
    logger.info(
        "Rules engine loaded with %d YAML rules and %d plugins",
        len(engine.rules),
        len(engine.plugins),
    )
    return engine
