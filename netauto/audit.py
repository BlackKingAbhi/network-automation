"""
audit.py - Simple security audit of saved Cisco IOS configuration files.

How it works:
  1. Read the security policy (policies/security_policy.yaml). It lists the
     checks to run and their severity (HIGH / MEDIUM / LOW).
  2. Read every *.cfg file in a folder (normally the latest backups).
  3. Run each check using plain string / regular-expression matching.
  4. Print PASS / FAIL for every check and write a Markdown report.

Each check is a small function that receives the configuration text and
returns (passed, detail). Keeping checks as small functions makes them easy
to read, test and extend.
"""

import glob
import os
import re
from datetime import datetime

import yaml

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def has_line(config, pattern):
    """Return True if any line of the config matches the regex pattern."""
    return re.search(pattern, config, re.MULTILINE) is not None


def get_vty_blocks(config):
    """
    Return a list of 'line vty' blocks.

    Example config:
        line vty 0 4
         login local
         transport input ssh
    returns: [{"header": "line vty 0 4",
               "lines": ["login local", "transport input ssh"]}]
    """
    blocks = []
    current = None
    for line in config.splitlines():
        if line.startswith("line vty"):
            current = {"header": line.strip(), "lines": []}
            blocks.append(current)
        elif current is not None and line.startswith(" "):
            current["lines"].append(line.strip())
        else:
            current = None  # any non-indented line ends the block
    return blocks


# ---------------------------------------------------------------------------
# Security checks - each returns (passed: bool, detail: str)
# ---------------------------------------------------------------------------
def check_ssh_version_2(config):
    """SSH version 2 must be configured ('ip ssh version 2')."""
    if has_line(config, r"^ip ssh version 2\s*$"):
        return True, "'ip ssh version 2' is configured"
    return False, "'ip ssh version 2' is missing (SSHv1 is insecure)"


def check_no_telnet(config):
    """Telnet must not be allowed on any VTY line."""
    blocks = get_vty_blocks(config)
    if not blocks:
        return False, "No 'line vty' section found - cannot confirm Telnet is disabled"

    problems = []
    for block in blocks:
        transport = [l for l in block["lines"] if l.startswith("transport input")]
        if not transport:
            # Not shown = IOS default, which allows Telnet on many versions.
            problems.append(f"{block['header']}: no 'transport input' (default may allow Telnet)")
            continue
        protocols = transport[-1].split()[2:]
        if "telnet" in protocols or "all" in protocols:
            problems.append(f"{block['header']}: '{transport[-1]}' allows Telnet")

    if problems:
        return False, "; ".join(problems)
    return True, "All VTY lines restrict remote access (no Telnet)"


def check_no_weak_enable(config):
    """Use 'enable secret' (hashed) and never 'enable password' (weak)."""
    if has_line(config, r"^enable password\s"):
        return False, "'enable password' is configured (stored in plain text or weak type 7)"
    if not has_line(config, r"^enable (algorithm-type \S+ )?secret\s"):
        return False, "No 'enable secret' configured"
    return True, "'enable secret' is used and 'enable password' is not present"


def check_ntp_server(config):
    """At least one NTP server must be configured (correct log timestamps)."""
    servers = re.findall(r"^ntp server (?:vrf \S+ )?(\S+)", config, re.MULTILINE)
    if servers:
        return True, f"NTP server(s) configured: {', '.join(servers)}"
    return False, "No 'ntp server' configured"


def check_remote_logging(config):
    """Logs must be sent to a remote syslog server."""
    hosts = re.findall(
        r"^logging (?:host )?(?:vrf \S+ )?(\d{1,3}(?:\.\d{1,3}){3})", config, re.MULTILINE
    )
    if hosts:
        return True, f"Remote syslog server(s): {', '.join(hosts)}"
    return False, "No 'logging host <ip>' configured"


def check_password_encryption(config):
    """'service password-encryption' must be enabled."""
    if has_line(config, r"^no service password-encryption"):
        return False, "'no service password-encryption' is configured"
    if has_line(config, r"^service password-encryption\s*$"):
        return True, "'service password-encryption' is enabled"
    return False, "'service password-encryption' is missing"


# Map the check IDs used in the YAML policy to the Python functions.
CHECK_FUNCTIONS = {
    "ssh_version_2": check_ssh_version_2,
    "no_telnet": check_no_telnet,
    "no_weak_enable_password": check_no_weak_enable,
    "ntp_server": check_ntp_server,
    "remote_logging": check_remote_logging,
    "password_encryption": check_password_encryption,
}


# ---------------------------------------------------------------------------
# Running the audit
# ---------------------------------------------------------------------------
def load_policy(policy_path):
    """Load the list of enabled checks from the YAML security policy."""
    with open(policy_path, "r", encoding="utf-8") as file:
        policy = yaml.safe_load(file) or {}

    checks = []
    for check in policy.get("checks", []):
        if not check.get("enabled", True):
            continue
        if check["id"] not in CHECK_FUNCTIONS:
            raise ValueError(f"Unknown check id in policy: {check['id']}")
        check["severity"] = check.get("severity", "MEDIUM").upper()
        if check["severity"] not in SEVERITY_ORDER:
            raise ValueError(f"Invalid severity for {check['id']}: {check['severity']}")
        checks.append(check)
    return checks


def audit_config(config_text, checks):
    """Run all checks against one configuration. Returns a list of result dicts."""
    results = []
    for check in checks:
        passed, detail = CHECK_FUNCTIONS[check["id"]](config_text)
        results.append(
            {
                "id": check["id"],
                "name": check.get("name", check["id"]),
                "severity": check["severity"],
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
                "remediation": check.get("remediation", ""),
            }
        )
    return results


def audit_directory(config_dir, checks):
    """Audit every *.cfg file in config_dir. Returns {device_name: [results]}."""
    files = sorted(glob.glob(os.path.join(config_dir, "*.cfg")))
    audit_results = {}
    for file_path in files:
        device_name = os.path.splitext(os.path.basename(file_path))[0]
        with open(file_path, "r", encoding="utf-8") as file:
            audit_results[device_name] = audit_config(file.read(), checks)
    return audit_results


def print_audit_results(audit_results):
    """Print PASS / FAIL for every check on every device."""
    for device, results in audit_results.items():
        print(f"\n=== {device} ===")
        for r in results:
            print(f"  [{r['status']}] [{r['severity']:<6}] {r['name']}")
            if r["status"] == "FAIL":
                print(f"         -> {r['detail']}")

    total_fail = sum(
        1 for results in audit_results.values() for r in results if r["status"] == "FAIL"
    )
    total = sum(len(results) for results in audit_results.values())
    print(f"\nAudit complete: {total - total_fail}/{total} checks passed, {total_fail} failed.")


def generate_markdown_report(audit_results, config_dir):
    """Build a readable Markdown security report and return it as a string."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Network Security Audit Report",
        "",
        f"- **Generated:** {now}",
        f"- **Configurations audited from:** `{config_dir}`",
        f"- **Devices audited:** {len(audit_results)}",
        "",
        "## Summary",
        "",
        "| Device | Passed | Failed | HIGH | MEDIUM | LOW |",
        "|--------|--------|--------|------|--------|-----|",
    ]

    for device, results in audit_results.items():
        failed = [r for r in results if r["status"] == "FAIL"]
        count = {sev: sum(1 for r in failed if r["severity"] == sev) for sev in SEVERITY_ORDER}
        lines.append(
            f"| {device} | {len(results) - len(failed)} | {len(failed)} | "
            f"{count['HIGH']} | {count['MEDIUM']} | {count['LOW']} |"
        )

    lines += ["", "## Detailed Results", ""]
    for device, results in audit_results.items():
        lines += [
            f"### {device}",
            "",
            "| Status | Severity | Check | Detail |",
            "|--------|----------|-------|--------|",
        ]
        for r in results:
            icon = "PASS" if r["status"] == "PASS" else "**FAIL**"
            detail = r["detail"].replace("|", "\\|")
            lines.append(f"| {icon} | {r['severity']} | {r['name']} | {detail} |")
        lines.append("")

    # Findings sorted by severity with the fix for each one.
    findings = [
        (device, r)
        for device, results in audit_results.items()
        for r in results
        if r["status"] == "FAIL"
    ]
    findings.sort(key=lambda item: SEVERITY_ORDER[item[1]["severity"]])

    lines += ["## Findings and Recommended Fixes", ""]
    if not findings:
        lines.append("No findings - all devices passed every check.")
    for device, r in findings:
        lines.append(f"- **[{r['severity']}] {device} - {r['name']}**: {r['detail']}")
        if r["remediation"]:
            lines.append(f"  - Fix: `{r['remediation']}`")

    lines += [
        "",
        "---",
        "*This report checks only the basic policies listed in "
        "`policies/security_policy.yaml`. A PASS does not mean a device is "
        "fully secure.*",
        "",
    ]
    return "\n".join(lines)


def write_report(report_text, report_dir, filename="security_audit_report.md"):
    """Save the Markdown report and return its path."""
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, filename)
    with open(path, "w", encoding="utf-8") as file:
        file.write(report_text)
    return path
