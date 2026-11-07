"""Unit tests for netauto/audit.py - no Cisco devices required."""

import os

import pytest

from netauto import audit

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
POLICY_PATH = os.path.join(PROJECT_ROOT, "policies", "security_policy.yaml")

# A configuration that satisfies every policy.
SECURE_CONFIG = """\
hostname R1
service password-encryption
enable secret 9 $9$EXAMPLEHASHONLY
ip ssh version 2
ntp server 192.168.150.10
logging host 192.168.150.20
line con 0
 login local
line vty 0 4
 login local
 transport input ssh
line vty 5 15
 login local
 transport input ssh
end
"""


@pytest.fixture
def checks():
    return audit.load_policy(POLICY_PATH)


def result_by_id(results, check_id):
    return next(r for r in results if r["id"] == check_id)


def test_policy_loads_six_checks(checks):
    assert len(checks) == 6
    assert {c["severity"] for c in checks} <= {"HIGH", "MEDIUM", "LOW"}


def test_secure_config_passes_all_checks(checks):
    results = audit.audit_config(SECURE_CONFIG, checks)
    failed = [r for r in results if r["status"] == "FAIL"]
    assert failed == [], failed


def test_detects_missing_ssh_version_2(checks):
    config = SECURE_CONFIG.replace("ip ssh version 2\n", "")
    result = result_by_id(audit.audit_config(config, checks), "ssh_version_2")
    assert result["status"] == "FAIL"
    assert result["severity"] == "HIGH"


def test_detects_telnet_enabled(checks):
    config = SECURE_CONFIG.replace(
        "line vty 0 4\n login local\n transport input ssh",
        "line vty 0 4\n login local\n transport input telnet ssh",
    )
    result = result_by_id(audit.audit_config(config, checks), "no_telnet")
    assert result["status"] == "FAIL"
    assert "line vty 0 4" in result["detail"]


def test_detects_transport_input_all(checks):
    config = SECURE_CONFIG.replace(" transport input ssh\nline vty 5 15", " transport input all\nline vty 5 15")
    assert result_by_id(audit.audit_config(config, checks), "no_telnet")["status"] == "FAIL"


def test_missing_transport_input_is_treated_as_fail(checks):
    # Without 'transport input' IOS uses its default, which may allow Telnet.
    config = SECURE_CONFIG.replace("line vty 5 15\n login local\n transport input ssh", "line vty 5 15\n login local")
    assert result_by_id(audit.audit_config(config, checks), "no_telnet")["status"] == "FAIL"


def test_detects_weak_enable_password(checks):
    config = SECURE_CONFIG.replace("enable secret 9 $9$EXAMPLEHASHONLY", "enable password FAKEPASS")
    result = result_by_id(audit.audit_config(config, checks), "no_weak_enable_password")
    assert result["status"] == "FAIL"


def test_detects_missing_ntp_logging_and_encryption(checks):
    config = (
        SECURE_CONFIG.replace("ntp server 192.168.150.10\n", "")
        .replace("logging host 192.168.150.20\n", "")
        .replace("service password-encryption\n", "")
    )
    results = audit.audit_config(config, checks)
    assert result_by_id(results, "ntp_server")["status"] == "FAIL"
    assert result_by_id(results, "remote_logging")["status"] == "FAIL"
    assert result_by_id(results, "password_encryption")["status"] == "FAIL"


def test_sample_lab_configurations_pass(checks):
    """The four sample lab configs shipped with the project must be compliant."""
    results = audit.audit_directory(os.path.join(PROJECT_ROOT, "configurations"), checks)
    assert sorted(results) == ["R1", "R2", "SW1", "SW2"]
    for device, device_results in results.items():
        assert all(r["status"] == "PASS" for r in device_results), device


def test_insecure_example_fails_every_check(checks):
    path = os.path.join(PROJECT_ROOT, "examples", "insecure_router_example.cfg")
    with open(path, encoding="utf-8") as file:
        results = audit.audit_config(file.read(), checks)
    assert all(r["status"] == "FAIL" for r in results)


def test_markdown_report_is_generated(tmp_path, checks):
    results = {"R1": audit.audit_config(SECURE_CONFIG.replace("ip ssh version 2\n", ""), checks)}
    report = audit.generate_markdown_report(results, "backups")
    path = audit.write_report(report, str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert text.startswith("# Network Security Audit Report")
    assert "| R1 | 5 | 1 | 1 | 0 | 0 |" in text
    assert "[HIGH] R1 - SSH version 2 must be configured" in text
