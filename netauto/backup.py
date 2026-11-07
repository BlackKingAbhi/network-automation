"""
backup.py - Back up the running configuration of every device.

For each device in the inventory:
  1. Connect over SSH (Netmiko).
  2. Run 'show running-config'.
  3. Remove a few lines that change on every run (timestamps etc.) so that
     Git only shows REAL configuration changes.
  4. Save the result as <device-name>.cfg in the backup folder.

Optionally, the backup folder can be a PRIVATE local Git repository and the
tool can commit the new backups automatically (netauto backup --commit).
"""

import os
import re
import subprocess
from datetime import datetime

from netauto.connection import DeviceConnectionError, connect_to_device

BACKUP_COMMAND = "show running-config"

# Lines that change even when nobody changed the configuration.
# Removing them keeps the Git history clean.
VOLATILE_LINE_PATTERNS = [
    r"^Building configuration",
    r"^Current configuration\s*:",
    r"^! Last configuration change",
    r"^! NVRAM config last updated",
    r"^! No configuration change since last restart",
    r"^ntp clock-period",
]


def clean_config(raw_config):
    """Remove volatile lines and leading blank lines from the raw output."""
    cleaned_lines = []
    for line in raw_config.splitlines():
        if any(re.match(pattern, line) for pattern in VOLATILE_LINE_PATTERNS):
            continue
        cleaned_lines.append(line.rstrip())

    # Drop blank lines at the very beginning of the output.
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)

    return "\n".join(cleaned_lines) + "\n"


def save_config(device_name, config_text, backup_dir):
    """Write the configuration to <backup_dir>/<device_name>.cfg and return the path."""
    os.makedirs(backup_dir, exist_ok=True)
    file_path = os.path.join(backup_dir, f"{device_name}.cfg")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(config_text)
    return file_path


def backup_device(device, credentials, backup_dir, settings=None):
    """
    Back up one device.

    Returns a result dict:
        {"device": "R1", "success": True,  "file": "backups/R1.cfg", "error": None}
        {"device": "R2", "success": False, "file": None, "error": "...message..."}
    """
    name = device["name"]
    try:
        connection = connect_to_device(device, credentials, settings)
    except DeviceConnectionError as error:
        return {"device": name, "success": False, "file": None, "error": str(error)}

    try:
        raw_config = connection.send_command(BACKUP_COMMAND, read_timeout=60)
    except Exception as error:
        return {
            "device": name,
            "success": False,
            "file": None,
            "error": f"{name}: failed to run '{BACKUP_COMMAND}': {error}",
        }
    finally:
        connection.disconnect()

    # A very short output usually means the command was rejected
    # (for example '% Invalid input' when not in enable mode).
    if "hostname" not in raw_config:
        return {
            "device": name,
            "success": False,
            "file": None,
            "error": f"{name}: output does not look like a configuration",
        }

    file_path = save_config(name, clean_config(raw_config), backup_dir)
    return {"device": name, "success": True, "file": file_path, "error": None}


def backup_all(devices, credentials, backup_dir, settings=None):
    """Back up every device in the inventory and return a list of results."""
    results = []
    for device in devices:
        print(f"[*] Backing up {device['name']} ({device['host']}) ...")
        result = backup_device(device, credentials, backup_dir, settings)
        if result["success"]:
            print(f"    [OK]   saved to {result['file']}")
        else:
            print(f"    [FAIL] {result['error']}")
        results.append(result)
    return results


def print_backup_summary(results):
    """Print a short summary table at the end of the backup run."""
    succeeded = [r["device"] for r in results if r["success"]]
    failed = [r["device"] for r in results if not r["success"]]
    print("\n========== Backup Summary ==========")
    print(f"Successful : {len(succeeded)}  {', '.join(succeeded)}")
    print(f"Failed     : {len(failed)}  {', '.join(failed)}")
    print("====================================")


def commit_backups(backup_dir):
    """
    Commit the backup folder to its own PRIVATE Git repository.

    The backup folder must already be a Git repository (run 'git init'
    inside it once). Returns True if a commit was created.
    """
    if not os.path.isdir(os.path.join(backup_dir, ".git")):
        print(
            f"[!] {backup_dir} is not a Git repository. To enable version tracking run:\n"
            f"      cd {backup_dir} && git init\n"
            "    (keep this repository PRIVATE - never push it to a public site)"
        )
        return False

    def git(*args):
        return subprocess.run(
            ["git", "-C", backup_dir, *args], capture_output=True, text=True
        )

    git("add", "--all")

    # 'git diff --cached --quiet' returns 0 when nothing is staged.
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("[i] No configuration changes since the last backup - nothing to commit.")
        return False

    message = f"Config backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = git("commit", "-m", message)
    if result.returncode != 0:
        print(f"[!] git commit failed: {result.stderr.strip()}")
        return False

    print(f"[OK] Committed backups to private Git repo: '{message}'")
    return True
