"""Tests for the YAML rules engine and Python plugin system."""

import textwrap

import pytest
from agentaudit_api.services.rules.engine import RuleEngine, _resolve_field
from agentaudit_api.services.rules.loader import (
    create_engine,
    load_custom_rules,
    load_yaml_file,
    load_yaml_string,
)
from agentaudit_api.services.rules.plugin import (
    PluginResult,
    PluginRule,
    clear_registry,
    get_registered_plugins,
    load_plugin_directory,
    load_plugin_file,
    rule,
)
from agentaudit_api.services.rules.schema import Condition, Effects, Rule

# --- Unit tests: condition evaluation ---


class TestConditionEvaluation:
    def _engine_with(self, yaml: str) -> RuleEngine:
        rules = load_yaml_string(yaml)
        return RuleEngine(rules)

    def test_eq_match(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: action
      eq: shell_command
    effects:
      risk_level: high
""")
        result = engine.evaluate({"action": "shell_command", "data": {}, "context": {}})
        assert result.risk_level == "high"

    def test_eq_no_match(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: action
      eq: shell_command
    effects:
      risk_level: high
""")
        result = engine.evaluate({"action": "file_read", "data": {}, "context": {}})
        assert result.risk_level == "low"

    def test_contains_case_insensitive(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: data.command
      contains: "DROP "
    effects:
      risk_level: critical
""")
        result = engine.evaluate(
            {
                "action": "shell_command",
                "data": {"command": "psql -c 'DROP TABLE users'"},
                "context": {},
            }
        )
        assert result.risk_level == "critical"

    def test_matches_regex(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: data
      matches: "sk_live_[a-zA-Z0-9]+"
    effects:
      risk_level: critical
""")
        result = engine.evaluate(
            {
                "action": "shell_command",
                "data": {"command": "curl -H 'sk_live_abc123'"},
                "context": {},
            }
        )
        assert result.risk_level == "critical"

    def test_all_combinator(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      all:
        - field: action
          eq: shell_command
        - field: data.command
          contains: prod
    effects:
      risk_level: high
""")
        # Both match
        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "ssh prod-db"}, "context": {}}
        )
        assert result.risk_level == "high"

        # Only one matches
        result = engine.evaluate(
            {"action": "file_read", "data": {"command": "ssh prod-db"}, "context": {}}
        )
        assert result.risk_level == "low"

    def test_any_combinator(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      any:
        - field: action
          contains: credential
        - field: action
          contains: password
    effects:
      risk_level: critical
""")
        result = engine.evaluate({"action": "access_credential", "data": {}, "context": {}})
        assert result.risk_level == "critical"

        result = engine.evaluate({"action": "read_password", "data": {}, "context": {}})
        assert result.risk_level == "critical"

        result = engine.evaluate({"action": "file_read", "data": {}, "context": {}})
        assert result.risk_level == "low"

    def test_not_combinator(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      all:
        - field: action
          eq: shell_command
        - not:
            field: data.command
            contains: "test"
    effects:
      risk_level: medium
""")
        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "deploy app"}, "context": {}}
        )
        assert result.risk_level == "medium"

        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "pytest tests/"}, "context": {}}
        )
        assert result.risk_level == "low"

    def test_nested_any_in_all(self):
        """Test the pattern used in built-in rules: all + nested any."""
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      all:
        - field: action
          eq: shell_command
        - any:
            - field: data.command
              contains: "rm -rf"
            - field: data.command
              contains: "DROP "
    effects:
      risk_level: critical
""")
        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "rm -rf /var"}, "context": {}}
        )
        assert result.risk_level == "critical"

        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "ls /var"}, "context": {}}
        )
        assert result.risk_level == "low"

    def test_exists_operator(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: data.file_path
      op: exists
      value: true
    effects:
      risk_level: medium
""")
        result = engine.evaluate(
            {"action": "file_read", "data": {"file_path": "/app/main.py"}, "context": {}}
        )
        assert result.risk_level == "medium"

        result = engine.evaluate(
            {"action": "shell_command", "data": {"command": "ls"}, "context": {}}
        )
        assert result.risk_level == "low"

    def test_in_operator(self):
        engine = self._engine_with("""
rules:
  - id: test
    name: test
    match:
      field: action
      op: in
      value: [file_read, file_write]
    effects:
      risk_level: medium
""")
        result = engine.evaluate({"action": "file_read", "data": {}, "context": {}})
        assert result.risk_level == "medium"

        result = engine.evaluate({"action": "shell_command", "data": {}, "context": {}})
        assert result.risk_level == "low"


# --- Unit tests: field resolution ---


class TestFieldResolution:
    def test_top_level_string(self):
        assert _resolve_field("action", {"action": "shell_command"}) == "shell_command"

    def test_nested_field(self):
        assert _resolve_field("data.command", {"data": {"command": "ls"}}) == "ls"

    def test_deep_nested(self):
        event = {"context": {"env": {"name": "production"}}}
        assert _resolve_field("context.env.name", event) == "production"

    def test_missing_field(self):
        assert _resolve_field("data.missing", {"data": {}}) is None

    def test_dict_flattened(self):
        result = _resolve_field("data", {"data": {"a": "hello", "b": "world"}})
        assert "hello" in result
        assert "world" in result

    def test_boolean_field(self):
        assert _resolve_field("pii_detected", {"pii_detected": True}) is True


# --- Integration: built-in rules produce correct risk levels ---


class TestBuiltinRules:
    """Test that the built-in YAML rules produce the same results as the old hardcoded scorer."""

    @pytest.fixture()
    def engine(self):
        return create_engine()

    def _eval(self, engine, action, data=None, context=None, pii_detected=False):
        event = {
            "action": action,
            "data": data or {},
            "context": context or {},
            "pii_detected": pii_detected,
        }
        return engine.evaluate(event)

    def test_credential_action(self, engine):
        assert self._eval(engine, "access_credential").risk_level == "critical"

    def test_password_action(self, engine):
        assert self._eval(engine, "read_password").risk_level == "critical"

    def test_api_key_in_data(self, engine):
        result = self._eval(
            engine,
            "shell_command",
            data={"command": "curl -H 'Authorization: sk_live_abc123def456'"},
        )
        assert result.risk_level == "critical"

    def test_github_token(self, engine):
        result = self._eval(
            engine,
            "shell_command",
            data={"command": "git clone https://ghp_abc123@github.com/repo"},
        )
        assert result.risk_level == "critical"

    def test_aws_key(self, engine):
        result = self._eval(
            engine, "shell_command", data={"command": "export AWS_KEY=AKIAIOSFODNN7EXAMPLE"}
        )
        assert result.risk_level == "critical"

    def test_rm_rf(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "rm -rf /var/data"})
        assert result.risk_level == "critical"

    def test_drop_table(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "psql -c 'DROP TABLE users'"})
        assert result.risk_level == "critical"

    def test_delete_from(self, engine):
        result = self._eval(
            engine, "shell_command", data={"command": "psql -c 'DELETE FROM users WHERE id=1'"}
        )
        assert result.risk_level == "critical"

    def test_prod_command(self, engine):
        result = self._eval(
            engine,
            "shell_command",
            data={"command": "psql -h prod-db.internal -c 'SELECT email FROM users'"},
        )
        assert result.risk_level == "high"

    def test_env_file_write(self, engine):
        result = self._eval(engine, "file_write", data={"file_path": "/app/.env"})
        assert result.risk_level == "high"

    def test_secret_file_write(self, engine):
        result = self._eval(engine, "file_write", data={"file_path": "/app/secrets.yaml"})
        assert result.risk_level == "high"

    def test_env_file_read(self, engine):
        result = self._eval(engine, "file_read", data={"file_path": "/app/.env.production"})
        assert result.risk_level == "high"

    def test_pem_file_read(self, engine):
        result = self._eval(engine, "file_read", data={"file_path": "/home/user/.ssh/id_rsa.pem"})
        assert result.risk_level == "high"

    def test_pii_production(self, engine):
        result = self._eval(
            engine, "access_record", context={"environment": "production"}, pii_detected=True
        )
        assert result.risk_level == "high"

    def test_pii_detected(self, engine):
        result = self._eval(engine, "access_record", pii_detected=True)
        assert result.risk_level == "medium"

    def test_sudo(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "sudo apt update"})
        assert result.risk_level == "medium"

    def test_chmod(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "chmod 777 /tmp/script.sh"})
        assert result.risk_level == "medium"

    def test_npm_install(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "npm install express"})
        assert result.risk_level == "low"

    def test_pip_install(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "pip install requests"})
        assert result.risk_level == "low"

    def test_innocuous(self, engine):
        result = self._eval(engine, "shell_command", data={"command": "pytest tests/ -v"})
        assert result.risk_level == "low"

    def test_normal_file_read(self, engine):
        result = self._eval(engine, "file_read", data={"file_path": "/app/main.py"})
        assert result.risk_level == "low"


# --- Test: effects and tags ---


class TestEffects:
    def test_tags_accumulated(self):
        rules = load_yaml_string("""
rules:
  - id: rule-a
    name: Rule A
    tags: [from-rule]
    match:
      field: action
      eq: test
    effects:
      risk_level: medium
      tags: [from-effects]
""")
        engine = RuleEngine(rules)
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert "from-rule" in result.tags
        assert "from-effects" in result.tags

    def test_highest_risk_wins(self):
        rules = load_yaml_string("""
rules:
  - id: medium-rule
    name: Medium
    match:
      field: action
      eq: test
    effects:
      risk_level: medium

  - id: high-rule
    name: High
    match:
      field: action
      eq: test
    effects:
      risk_level: high
""")
        engine = RuleEngine(rules)
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "high"
        assert len(result.matched_rules) == 2

    def test_block_effect(self):
        rules = load_yaml_string("""
rules:
  - id: blocker
    name: Blocker
    match:
      field: action
      eq: dangerous
    effects:
      risk_level: critical
      block: true
""")
        engine = RuleEngine(rules)
        result = engine.evaluate({"action": "dangerous", "data": {}, "context": {}})
        assert result.block is True

    def test_disabled_rule_skipped(self):
        rules = load_yaml_string("""
rules:
  - id: disabled
    name: Disabled
    enabled: false
    match:
      field: action
      eq: test
    effects:
      risk_level: critical
""")
        engine = RuleEngine(rules)
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "low"
        assert len(result.matched_rules) == 0

    def test_frameworks_merged(self):
        rules = load_yaml_string("""
rules:
  - id: rule-a
    name: A
    match:
      field: action
      eq: test
    effects:
      risk_level: medium
      frameworks:
        gdpr: data_processing

  - id: rule-b
    name: B
    match:
      field: action
      eq: test
    effects:
      risk_level: medium
      frameworks:
        soc2: access_control
""")
        engine = RuleEngine(rules)
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.frameworks["gdpr"] == "data_processing"
        assert result.frameworks["soc2"] == "access_control"


# --- Test: engine management ---


class TestEngineManagement:
    def test_add_and_remove_rule(self):
        engine = RuleEngine()
        rule = Rule(
            id="test",
            name="Test",
            match=Condition(field="action", eq="test"),
            effects=Effects(risk_level="high"),
        )
        engine.add_rule(rule)
        assert len(engine.rules) == 1

        removed = engine.remove_rule("test")
        assert removed is True
        assert len(engine.rules) == 0

    def test_remove_nonexistent(self):
        engine = RuleEngine()
        assert engine.remove_rule("nope") is False


# --- Test: score_risk backward compatibility ---


class TestScoreRiskCompat:
    """Ensure the public score_risk() API still works."""

    def test_score_risk_returns_string(self):
        from agentaudit_api.services.risk_scorer import reset_engine, score_risk

        reset_engine()
        result = score_risk("access_credential", {}, {}, pii_detected=False)
        assert result == "critical"

    def test_score_risk_innocuous(self):
        from agentaudit_api.services.risk_scorer import reset_engine, score_risk

        reset_engine()
        result = score_risk("shell_command", {"command": "ls"}, {}, pii_detected=False)
        assert result == "low"


# --- Python plugin tests ---


class TestPluginDecorator:
    """Test the @rule decorator and plugin registry."""

    def setup_method(self):
        clear_registry()

    def teardown_method(self):
        clear_registry()

    def test_decorator_registers_plugin(self):
        @rule(id="test-plugin", name="Test Plugin", severity="high", category="security")
        def my_rule(event):
            return PluginResult(risk_level="high")

        plugins = get_registered_plugins()
        assert len(plugins) == 1
        assert plugins[0].id == "test-plugin"
        assert plugins[0].name == "Test Plugin"
        assert plugins[0].severity == "high"
        assert plugins[0].fn is my_rule

    def test_decorator_preserves_function(self):
        @rule(id="test-plugin", name="Test")
        def my_rule(event):
            return PluginResult(risk_level="medium")

        # Function is still callable directly
        result = my_rule({"action": "test"})
        assert result.risk_level == "medium"

    def test_plugin_with_tags(self):
        @rule(id="tagged", name="Tagged", tags=["custom", "security"])
        def tagged_rule(event):
            return PluginResult(risk_level="low")

        plugins = get_registered_plugins()
        assert plugins[0].tags == ["custom", "security"]

    def test_clear_registry(self):
        @rule(id="temp", name="Temp")
        def temp_rule(event):
            return None

        assert len(get_registered_plugins()) == 1
        clear_registry()
        assert len(get_registered_plugins()) == 0


class TestPluginEvaluation:
    """Test that Python plugin rules are evaluated correctly by the engine."""

    def test_plugin_match_sets_risk(self):
        plugin = PluginRule(
            id="test-plugin",
            name="Test Plugin",
            description="",
            severity="critical",
            category="security",
            tags=["plugin-tag"],
            enabled=True,
            fn=lambda event: PluginResult(risk_level="critical", tags=["detected"]),
        )
        engine = RuleEngine(plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "critical"
        assert len(result.matched_rules) == 1
        assert result.matched_rules[0].rule_id == "test-plugin"
        assert "plugin-tag" in result.tags
        assert "detected" in result.tags

    def test_plugin_no_match_returns_none(self):
        plugin = PluginRule(
            id="selective",
            name="Selective",
            description="",
            severity="high",
            category="security",
            tags=[],
            enabled=True,
            fn=lambda event: (
                PluginResult(risk_level="high") if event.get("action") == "dangerous" else None
            ),
        )
        engine = RuleEngine(plugins=[plugin])

        result = engine.evaluate({"action": "safe", "data": {}, "context": {}})
        assert result.risk_level == "low"
        assert len(result.matched_rules) == 0

        result = engine.evaluate({"action": "dangerous", "data": {}, "context": {}})
        assert result.risk_level == "high"
        assert len(result.matched_rules) == 1

    def test_disabled_plugin_skipped(self):
        plugin = PluginRule(
            id="disabled",
            name="Disabled Plugin",
            description="",
            severity="critical",
            category="security",
            tags=[],
            enabled=False,
            fn=lambda event: PluginResult(risk_level="critical"),
        )
        engine = RuleEngine(plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "low"

    def test_plugin_block_effect(self):
        plugin = PluginRule(
            id="blocker",
            name="Blocker Plugin",
            description="",
            severity="critical",
            category="security",
            tags=[],
            enabled=True,
            fn=lambda event: PluginResult(risk_level="critical", block=True),
        )
        engine = RuleEngine(plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.block is True

    def test_plugin_frameworks(self):
        plugin = PluginRule(
            id="gdpr-plugin",
            name="GDPR Plugin",
            description="",
            severity="high",
            category="privacy",
            tags=[],
            enabled=True,
            fn=lambda event: PluginResult(
                risk_level="high",
                frameworks={"gdpr": "right_to_erasure"},
            ),
        )
        engine = RuleEngine(plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.frameworks["gdpr"] == "right_to_erasure"

    def test_plugin_error_does_not_crash(self):
        """Plugin that raises should be caught, not crash the engine."""

        def bad_plugin(event):
            raise ValueError("intentional error")

        plugin = PluginRule(
            id="bad",
            name="Bad Plugin",
            description="",
            severity="critical",
            category="security",
            tags=[],
            enabled=True,
            fn=bad_plugin,
        )
        engine = RuleEngine(plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "low"
        assert len(result.matched_rules) == 0


class TestPluginWithYamlRules:
    """Test that YAML rules and Python plugins work together in one engine."""

    def test_yaml_and_plugin_both_fire(self):
        yaml_rules = load_yaml_string("""
rules:
  - id: yaml-rule
    name: YAML Rule
    match:
      field: action
      eq: test
    effects:
      risk_level: medium
      tags: [from-yaml]
""")
        plugin = PluginRule(
            id="python-rule",
            name="Python Rule",
            description="",
            severity="high",
            category="security",
            tags=["from-plugin"],
            enabled=True,
            fn=lambda event: PluginResult(risk_level="high", tags=["plugin-effect"]),
        )

        engine = RuleEngine(rules=yaml_rules, plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})

        assert result.risk_level == "high"  # Plugin wins (higher)
        assert len(result.matched_rules) == 2
        rule_ids = {m.rule_id for m in result.matched_rules}
        assert "yaml-rule" in rule_ids
        assert "python-rule" in rule_ids
        assert "from-yaml" in result.tags
        assert "from-plugin" in result.tags
        assert "plugin-effect" in result.tags

    def test_yaml_overrides_plugin_when_higher(self):
        yaml_rules = load_yaml_string("""
rules:
  - id: yaml-critical
    name: YAML Critical
    match:
      field: action
      eq: test
    effects:
      risk_level: critical
""")
        plugin = PluginRule(
            id="python-medium",
            name="Python Medium",
            description="",
            severity="medium",
            category="general",
            tags=[],
            enabled=True,
            fn=lambda event: PluginResult(risk_level="medium"),
        )

        engine = RuleEngine(rules=yaml_rules, plugins=[plugin])
        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "critical"

    def test_remove_plugin_by_id(self):
        plugin = PluginRule(
            id="removable",
            name="Removable",
            description="",
            severity="high",
            category="security",
            tags=[],
            enabled=True,
            fn=lambda event: PluginResult(risk_level="high"),
        )
        engine = RuleEngine(plugins=[plugin])
        assert len(engine.plugins) == 1

        removed = engine.remove_rule("removable")
        assert removed is True
        assert len(engine.plugins) == 0

        result = engine.evaluate({"action": "test", "data": {}, "context": {}})
        assert result.risk_level == "low"


class TestPluginFileLoading:
    """Test loading Python plugins from files."""

    def setup_method(self):
        clear_registry()

    def teardown_method(self):
        clear_registry()

    def test_load_plugin_from_file(self, tmp_path):
        plugin_file = tmp_path / "my_rules.py"
        plugin_file.write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(
                id="file-loaded-rule",
                name="File Loaded Rule",
                severity="high",
                category="security",
            )
            def detect_something(event):
                if "dangerous" in event.get("action", ""):
                    return PluginResult(risk_level="high", tags=["from-file"])
                return None
        """)
        )

        plugins = load_plugin_file(plugin_file)
        assert len(plugins) == 1
        assert plugins[0].id == "file-loaded-rule"

        # Verify it actually works
        engine = RuleEngine(plugins=plugins)
        result = engine.evaluate({"action": "dangerous_action", "data": {}, "context": {}})
        assert result.risk_level == "high"
        assert "from-file" in result.tags

        result = engine.evaluate({"action": "safe_action", "data": {}, "context": {}})
        assert result.risk_level == "low"

    def test_load_plugin_directory(self, tmp_path):
        # Create two plugin files
        (tmp_path / "rule_a.py").write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(id="plugin-a", name="Plugin A", severity="medium")
            def rule_a(event):
                if event.get("action") == "action_a":
                    return PluginResult(risk_level="medium")
                return None
        """)
        )
        (tmp_path / "rule_b.py").write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(id="plugin-b", name="Plugin B", severity="high")
            def rule_b(event):
                if event.get("action") == "action_b":
                    return PluginResult(risk_level="high")
                return None
        """)
        )
        # Files starting with _ should be skipped
        (tmp_path / "_ignored.py").write_text("raise Exception('should not be loaded')")

        plugins = load_plugin_directory(tmp_path)
        assert len(plugins) == 2
        ids = {p.id for p in plugins}
        assert "plugin-a" in ids
        assert "plugin-b" in ids

    def test_broken_plugin_file_skipped(self, tmp_path):
        (tmp_path / "good.py").write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(id="good-plugin", name="Good Plugin")
            def good(event):
                return PluginResult(risk_level="low")
        """)
        )
        (tmp_path / "bad.py").write_text("raise SyntaxError('broken')")

        plugins = load_plugin_directory(tmp_path)
        # Good plugin still loads despite bad one failing
        assert len(plugins) == 1
        assert plugins[0].id == "good-plugin"


class TestCustomYamlFileLoading:
    """Test loading custom YAML rules from files and directories."""

    def test_load_yaml_from_file(self, tmp_path):
        rule_file = tmp_path / "custom_rules.yaml"
        rule_file.write_text(
            textwrap.dedent("""\
            rules:
              - id: custom-file-rule
                name: Custom File Rule
                severity: high
                category: security
                match:
                  field: data.command
                  contains: "internal-tool"
                effects:
                  risk_level: high
                  tags: [custom, internal]
        """)
        )

        rules = load_yaml_file(rule_file)
        assert len(rules) == 1
        assert rules[0].id == "custom-file-rule"

        engine = RuleEngine(rules=rules)
        result = engine.evaluate(
            {
                "action": "shell_command",
                "data": {"command": "internal-tool --deploy"},
                "context": {},
            }
        )
        assert result.risk_level == "high"
        assert "custom" in result.tags

    def test_load_custom_rules_directory(self, tmp_path):
        (tmp_path / "team_rules.yaml").write_text(
            textwrap.dedent("""\
            rules:
              - id: team-rule-1
                name: Team Rule 1
                match:
                  field: agent_id
                  eq: rogue-agent
                effects:
                  risk_level: critical
                  block: true
        """)
        )
        (tmp_path / "compliance_rules.yaml").write_text(
            textwrap.dedent("""\
            rules:
              - id: compliance-rule-1
                name: Compliance Rule 1
                match:
                  field: context.region
                  eq: eu-west-1
                effects:
                  risk_level: medium
                  frameworks:
                    gdpr: cross_border_transfer
        """)
        )

        rules = load_custom_rules(tmp_path)
        assert len(rules) == 2
        ids = {r.id for r in rules}
        assert "team-rule-1" in ids
        assert "compliance-rule-1" in ids

        # Verify source tracking
        for r in rules:
            assert r.source.startswith("custom:")

    def test_custom_yaml_nonexistent_dir(self, tmp_path):
        rules = load_custom_rules(tmp_path / "nonexistent")
        assert rules == []

    def test_empty_yaml_file(self, tmp_path):
        (tmp_path / "empty.yaml").write_text("")
        rules = load_yaml_file(tmp_path / "empty.yaml")
        assert rules == []


class TestCreateEngineWithPlugins:
    """Test the create_engine factory with plugin_dirs."""

    def setup_method(self):
        clear_registry()

    def teardown_method(self):
        clear_registry()

    def test_engine_with_builtin_and_plugins(self, tmp_path):
        (tmp_path / "my_plugin.py").write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(id="engine-test-plugin", name="Engine Test Plugin", severity="critical")
            def detect_internal(event):
                cmd = (event.get("data") or {}).get("command", "")
                if "INTERNAL_SECRET" in cmd:
                    return PluginResult(risk_level="critical", tags=["internal-secret"])
                return None
        """)
        )

        engine = create_engine(include_builtin=True, plugin_dirs=[tmp_path])

        # Built-in rules should still work
        result = engine.evaluate({"action": "access_credential", "data": {}, "context": {}})
        assert result.risk_level == "critical"

        # Plugin should also work
        result = engine.evaluate(
            {
                "action": "shell_command",
                "data": {"command": "echo INTERNAL_SECRET=abc123"},
                "context": {},
            }
        )
        assert result.risk_level == "critical"
        assert "internal-secret" in result.tags

        # Something that matches neither
        result = engine.evaluate(
            {"action": "file_read", "data": {"file_path": "/app/main.py"}, "context": {}}
        )
        assert result.risk_level == "low"

    def test_engine_with_custom_yaml_and_plugins(self, tmp_path):
        yaml_dir = tmp_path / "yaml"
        yaml_dir.mkdir()
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        (yaml_dir / "rules.yaml").write_text(
            textwrap.dedent("""\
            rules:
              - id: yaml-custom
                name: YAML Custom
                match:
                  field: action
                  eq: custom_action
                effects:
                  risk_level: medium
                  tags: [yaml-custom]
        """)
        )
        (plugin_dir / "plugin.py").write_text(
            textwrap.dedent("""\
            from agentaudit_api.services.rules.plugin import rule, PluginResult

            @rule(id="py-custom", name="Python Custom", severity="high")
            def custom(event):
                if event.get("action") == "custom_action":
                    return PluginResult(risk_level="high", tags=["py-custom"])
                return None
        """)
        )

        engine = create_engine(
            include_builtin=False,
            custom_dirs=[yaml_dir],
            plugin_dirs=[plugin_dir],
        )

        assert len(engine.rules) == 1
        assert len(engine.plugins) == 1

        result = engine.evaluate({"action": "custom_action", "data": {}, "context": {}})
        assert result.risk_level == "high"  # Plugin wins
        assert "yaml-custom" in result.tags
        assert "py-custom" in result.tags
        assert len(result.matched_rules) == 2


class TestPluginComplexLogic:
    """Test that plugins can handle logic too complex for YAML."""

    def test_cross_field_correlation(self):
        """Plugin that correlates multiple fields with custom logic."""

        def cross_field_check(event):
            data = event.get("data") or {}
            context = event.get("context") or {}
            # Flag: agent writing to sensitive path outside working hours
            file_path = data.get("file_path", "")
            hour = context.get("hour")
            if (
                any(s in file_path for s in [".env", "secret"])
                and hour is not None
                and (hour < 6 or hour > 22)
            ):
                return PluginResult(
                    risk_level="critical",
                    tags=["after-hours-sensitive-write"],
                    block=True,
                )
            return None

        plugin = PluginRule(
            id="after-hours",
            name="After Hours Sensitive Write",
            description="Blocks sensitive file writes outside business hours",
            severity="critical",
            category="security",
            tags=["custom"],
            enabled=True,
            fn=cross_field_check,
        )
        engine = RuleEngine(plugins=[plugin])

        # After hours + sensitive file → critical + block
        result = engine.evaluate(
            {
                "action": "file_write",
                "data": {"file_path": "/app/.env.production"},
                "context": {"hour": 3},
            }
        )
        assert result.risk_level == "critical"
        assert result.block is True
        assert "after-hours-sensitive-write" in result.tags

        # Business hours + sensitive file → no match
        result = engine.evaluate(
            {
                "action": "file_write",
                "data": {"file_path": "/app/.env.production"},
                "context": {"hour": 14},
            }
        )
        assert result.risk_level == "low"

        # After hours + normal file → no match
        result = engine.evaluate(
            {
                "action": "file_write",
                "data": {"file_path": "/app/main.py"},
                "context": {"hour": 3},
            }
        )
        assert result.risk_level == "low"

    def test_stateful_rate_detection(self):
        """Plugin that tracks state (e.g., counting rapid actions)."""
        action_counts: dict[str, int] = {}

        def rate_detector(event):
            agent_id = event.get("agent_id", "unknown")
            action_counts[agent_id] = action_counts.get(agent_id, 0) + 1
            if action_counts[agent_id] > 3:
                return PluginResult(
                    risk_level="high",
                    tags=["rapid-fire"],
                )
            return None

        plugin = PluginRule(
            id="rate-detect",
            name="Rate Detector",
            description="",
            severity="high",
            category="operational",
            tags=[],
            enabled=True,
            fn=rate_detector,
        )
        engine = RuleEngine(plugins=[plugin])
        event = {"action": "shell_command", "data": {}, "context": {}, "agent_id": "bot-1"}

        # First 3 calls — no match
        for _ in range(3):
            result = engine.evaluate(event)
            assert result.risk_level == "low"

        # 4th call — triggers
        result = engine.evaluate(event)
        assert result.risk_level == "high"
        assert "rapid-fire" in result.tags
