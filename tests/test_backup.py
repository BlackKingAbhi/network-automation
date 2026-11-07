"""
Unit tests for netauto/backup.py.

The SSH connection is replaced with a fake (mock) object, so these tests
run without any Cisco device or network access.
"""

import os
from unittest.mock import MagicMock

from netauto import backup
from netauto.connection import DeviceConnectionError

DEVICE = {"name": "R1", "host": "192.168.150.101", "device_type": "cisco_ios", "role": "router"}
CREDENTIALS = {"username": "testuser", "password": "not-a-real-password", "secret": ""}

FAKE_RUNNING_CONFIG = """\
Building configuration...

Current configuration : 1234 bytes
!
! Last configuration change at 10:15:01 UTC Mon Nov 2 2026 by netadmin
!
version 15.9
hostname R1
!
ntp clock-period 17179869
ip ssh version 2
end
"""


def make_fake_connection(output=FAKE_RUNNING_CONFIG):
    connection = MagicMock()
    connection.send_command.return_value = output
    return connection


def test_backup_saves_configuration_with_mocked_ssh(tmp_path, monkeypatch):
    fake_conn = make_fake_connection()
    monkeypatch.setattr(backup, "connect_to_device", lambda *args, **kwargs: fake_conn)

    result = backup.backup_device(DEVICE, CREDENTIALS, str(tmp_path))

    assert result["success"] is True
    assert result["file"] == os.path.join(str(tmp_path), "R1.cfg")
    saved = open(result["file"], encoding="utf-8").read()
    assert "hostname R1" in saved
    assert "ip ssh version 2" in saved
    fake_conn.send_command.assert_called_once_with("show running-config", read_timeout=60)
    fake_conn.disconnect.assert_called_once()


def test_backup_removes_volatile_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "connect_to_device", lambda *a, **k: make_fake_connection())
    result = backup.backup_device(DEVICE, CREDENTIALS, str(tmp_path))
    saved = open(result["file"], encoding="utf-8").read()
    assert "Building configuration" not in saved
    assert "Current configuration" not in saved
    assert "Last configuration change" not in saved
    assert "ntp clock-period" not in saved
    assert saved.startswith("!")


def test_backup_all_uses_device_names_as_filenames(tmp_path, monkeypatch):
    devices = [dict(DEVICE, name=n) for n in ("R1", "R2", "SW1", "SW2")]
    monkeypatch.setattr(backup, "connect_to_device", lambda *a, **k: make_fake_connection())
    results = backup.backup_all(devices, CREDENTIALS, str(tmp_path))
    assert all(r["success"] for r in results)
    assert sorted(os.listdir(tmp_path)) == ["R1.cfg", "R2.cfg", "SW1.cfg", "SW2.cfg"]


def test_backup_handles_authentication_failure(tmp_path, monkeypatch):
    def failing_connect(*args, **kwargs):
        raise DeviceConnectionError("R1 (192.168.150.101): authentication failed")

    monkeypatch.setattr(backup, "connect_to_device", failing_connect)
    result = backup.backup_device(DEVICE, CREDENTIALS, str(tmp_path))
    assert result["success"] is False
    assert "authentication failed" in result["error"]
    assert os.listdir(tmp_path) == []  # nothing saved


def test_backup_rejects_invalid_output(tmp_path, monkeypatch):
    fake_conn = make_fake_connection(output="% Invalid input detected at '^' marker.")
    monkeypatch.setattr(backup, "connect_to_device", lambda *a, **k: fake_conn)
    result = backup.backup_device(DEVICE, CREDENTIALS, str(tmp_path))
    assert result["success"] is False
    fake_conn.disconnect.assert_called_once()


def test_connection_errors_are_translated(monkeypatch):
    """connect_to_device must turn Netmiko exceptions into DeviceConnectionError."""
    import pytest
    from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

    from netauto import connection

    for netmiko_error, expected in (
        (NetmikoTimeoutException, "timed out"),
        (NetmikoAuthenticationException, "authentication failed"),
    ):
        def raise_error(**kwargs):
            raise netmiko_error("simulated")

        monkeypatch.setattr(connection, "ConnectHandler", raise_error)
        with pytest.raises(DeviceConnectionError, match=expected):
            connection.connect_to_device(DEVICE, CREDENTIALS)


def test_commit_backups_with_private_git_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    backup.save_config("R1", "hostname R1\n", str(tmp_path))

    assert backup.commit_backups(str(tmp_path)) is True
    # Second run with no changes must not create an empty commit.
    assert backup.commit_backups(str(tmp_path)) is False


def test_commit_backups_without_git_repo(tmp_path):
    assert backup.commit_backups(str(tmp_path)) is False
