from agentaudit_api.services.risk_scorer import score_risk


def test_risk_credential_action():
    assert score_risk("access_credential", {}, {}, pii_detected=False) == "critical"


def test_risk_api_key_in_data():
    result = score_risk(
        "shell_command",
        {"command": "curl -H 'Authorization: sk_live_abc123def456'"},
        {},
        pii_detected=False,
    )
    assert result == "critical"


def test_risk_rm_rf():
    result = score_risk(
        "shell_command", {"command": "rm -rf /var/data"}, {}, pii_detected=False
    )
    assert result == "critical"


def test_risk_drop_table():
    result = score_risk(
        "shell_command",
        {"command": "psql -c 'DROP TABLE users'"},
        {},
        pii_detected=False,
    )
    assert result == "critical"


def test_risk_delete_from():
    result = score_risk(
        "shell_command",
        {"command": "psql -c 'DELETE FROM users WHERE id=1'"},
        {},
        pii_detected=False,
    )
    assert result == "critical"


def test_risk_prod_command():
    result = score_risk(
        "shell_command",
        {"command": "psql -h prod-db.internal -c 'SELECT email FROM users'"},
        {},
        pii_detected=False,
    )
    assert result == "high"


def test_risk_env_file_write():
    result = score_risk(
        "file_write", {"file_path": "/app/.env"}, {}, pii_detected=False
    )
    assert result == "high"


def test_risk_secret_file_write():
    result = score_risk(
        "file_write", {"file_path": "/app/secrets.yaml"}, {}, pii_detected=False
    )
    assert result == "high"


def test_risk_env_file_read():
    result = score_risk(
        "file_read", {"file_path": "/app/.env.production"}, {}, pii_detected=False
    )
    assert result == "high"


def test_risk_pem_file_read():
    result = score_risk(
        "file_read", {"file_path": "/home/user/.ssh/id_rsa.pem"}, {}, pii_detected=False
    )
    assert result == "high"


def test_risk_pii_production():
    result = score_risk(
        "access_record", {}, {"environment": "production"}, pii_detected=True
    )
    assert result == "high"


def test_risk_pii_detected():
    result = score_risk(
        "access_record", {}, {}, pii_detected=True
    )
    assert result == "medium"


def test_risk_sudo():
    result = score_risk(
        "shell_command", {"command": "sudo apt update"}, {}, pii_detected=False
    )
    assert result == "medium"


def test_risk_chmod():
    result = score_risk(
        "shell_command", {"command": "chmod 777 /tmp/script.sh"}, {}, pii_detected=False
    )
    assert result == "medium"


def test_risk_npm_install():
    result = score_risk(
        "shell_command", {"command": "npm install express"}, {}, pii_detected=False
    )
    assert result == "low"


def test_risk_pip_install():
    result = score_risk(
        "shell_command", {"command": "pip install requests"}, {}, pii_detected=False
    )
    assert result == "low"


def test_risk_innocuous():
    result = score_risk(
        "shell_command", {"command": "pytest tests/ -v"}, {}, pii_detected=False
    )
    assert result == "low"


def test_risk_file_read_normal():
    result = score_risk(
        "file_read", {"file_path": "/app/main.py"}, {}, pii_detected=False
    )
    assert result == "low"


# --- Integration tests: ingest via API and check risk_level ---


def test_ingest_prod_command(client, api_key_raw):
    """POST event with 'psql -h prod' → risk_level='high'."""
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "claude-code",
            "action": "shell_command",
            "data": {"command": "psql -h prod-db.internal -c 'SELECT * FROM users'"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    assert response.json()["risk_level"] == "high"


def test_ingest_env_file_read(client, api_key_raw):
    """POST event reading .env file → risk_level='high'."""
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "claude-code",
            "action": "file_read",
            "data": {"file_path": "/app/.env.production"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    assert response.json()["risk_level"] == "high"


def test_ingest_innocuous(client, api_key_raw):
    """POST innocuous event → risk_level='low'."""
    response = client.post(
        "/v1/events",
        json={
            "agent_id": "claude-code",
            "action": "shell_command",
            "data": {"command": "pytest tests/ -v"},
        },
        headers={"Authorization": f"Bearer {api_key_raw}"},
    )
    assert response.status_code == 201
    assert response.json()["risk_level"] == "low"
