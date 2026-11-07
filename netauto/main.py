"""
main.py - Command-line interface for the netauto tool.

Usage:
    netauto check     Verify SSH connectivity to every device
    netauto backup    Back up running configurations
    netauto audit     Run security checks on saved configurations
    netauto verify    Check interfaces, routing and OSPF neighbours

Run 'netauto <command> --help' for the options of each command.
"""

import argparse
import os
import sys

from netauto import __version__
from netauto.audit import (
    audit_directory,
    generate_markdown_report,
    load_policy,
    print_audit_results,
    write_report,
)
from netauto.backup import backup_all, commit_backups, print_backup_summary
from netauto.connection import (
    DeviceConnectionError,
    connect_to_device,
    get_credentials,
    get_hostname,
    load_inventory,
)
from netauto.verify import verify_all

DEFAULT_INVENTORY = os.path.join("inventory", "devices.yaml")
DEFAULT_POLICY = os.path.join("policies", "security_policy.yaml")
DEFAULT_REPORT_DIR = "reports"
# The backup folder can be overridden with --backup-dir or this variable.
DEFAULT_BACKUP_DIR = os.environ.get("NETAUTO_BACKUP_DIR", "backups")


# ---------------------------------------------------------------------------
# Command handlers - each returns an exit code (0 = success)
# ---------------------------------------------------------------------------
def cmd_check(args):
    """Try to log in to every device and show its hostname."""
    devices, settings = load_inventory(args.inventory)
    credentials = get_credentials()
    reachable = 0

    print(f"\nChecking SSH connectivity to {len(devices)} device(s)...\n")
    for device in devices:
        try:
            connection = connect_to_device(device, credentials, settings)
            hostname = get_hostname(connection)
            connection.disconnect()
            print(f"  [OK]   {device['name']:<5} {device['host']:<17} hostname: {hostname}")
            reachable += 1
        except DeviceConnectionError as error:
            print(f"  [FAIL] {error}")

    print(f"\n{reachable}/{len(devices)} device(s) reachable via SSH.")
    return 0 if reachable == len(devices) else 1


def cmd_backup(args):
    """Back up every device, then optionally commit to the private Git repo."""
    devices, settings = load_inventory(args.inventory)
    credentials = get_credentials()

    print(f"\nBacking up {len(devices)} device(s) to '{args.backup_dir}'...\n")
    results = backup_all(devices, credentials, args.backup_dir, settings)
    print_backup_summary(results)

    if args.commit and any(r["success"] for r in results):
        commit_backups(args.backup_dir)

    return 0 if all(r["success"] for r in results) else 1


def cmd_audit(args):
    """Audit the saved configuration files and write a Markdown report."""
    checks = load_policy(args.policy)
    results = audit_directory(args.config_dir, checks)

    if not results:
        print(
            f"No .cfg files found in '{args.config_dir}'.\n"
            "Run 'netauto backup' first, or audit the sample configs with:\n"
            "  netauto audit --config-dir configurations"
        )
        return 1

    print(f"\nAuditing {len(results)} configuration file(s) from '{args.config_dir}'")
    print_audit_results(results)

    report_path = write_report(
        generate_markdown_report(results, args.config_dir), args.report_dir
    )
    print(f"Markdown report written to: {report_path}")

    any_fail = any(r["status"] == "FAIL" for res in results.values() for r in res)
    return 1 if any_fail else 0


def cmd_verify(args):
    """Check interface status, routing table and OSPF neighbours."""
    devices, settings = load_inventory(args.inventory)
    credentials = get_credentials()
    results = verify_all(devices, credentials, settings)

    healthy = [r["hostname"] for r in results if not r["problems"]]
    print("\n========== Verification Summary ==========")
    print(f"Healthy devices      : {len(healthy)}/{len(results)}")
    for r in results:
        if r["problems"]:
            print(f"  {r['hostname']}: {len(r['problems'])} problem(s)")
    print("==========================================")
    return 0 if len(healthy) == len(results) else 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        prog="netauto",
        description="Network Configuration Backup & Security Auditing Automation "
        "for Cisco IOS routers and switches.",
        epilog="Credentials are read from NETAUTO_USERNAME / NETAUTO_PASSWORD / "
        "NETAUTO_ENABLE_SECRET or asked for securely at runtime.",
    )
    parser.add_argument("--version", action="version", version=f"netauto {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    inventory_help = f"device inventory YAML file (default: {DEFAULT_INVENTORY})"

    p_check = sub.add_parser("check", help="connect to all devices and verify SSH connectivity")
    p_check.add_argument("--inventory", default=DEFAULT_INVENTORY, help=inventory_help)
    p_check.set_defaults(func=cmd_check)

    p_backup = sub.add_parser("backup", help="back up all device running configurations")
    p_backup.add_argument("--inventory", default=DEFAULT_INVENTORY, help=inventory_help)
    p_backup.add_argument(
        "--backup-dir", default=DEFAULT_BACKUP_DIR,
        help=f"folder to save <device>.cfg files (default: {DEFAULT_BACKUP_DIR})",
    )
    p_backup.add_argument(
        "--commit", action="store_true",
        help="commit the backups to the private Git repository in the backup folder",
    )
    p_backup.set_defaults(func=cmd_backup)

    p_audit = sub.add_parser("audit", help="run security checks on the latest saved backups")
    p_audit.add_argument(
        "--config-dir", default=DEFAULT_BACKUP_DIR,
        help=f"folder containing .cfg files to audit (default: {DEFAULT_BACKUP_DIR})",
    )
    p_audit.add_argument("--policy", default=DEFAULT_POLICY,
                         help=f"security policy YAML (default: {DEFAULT_POLICY})")
    p_audit.add_argument("--report-dir", default=DEFAULT_REPORT_DIR,
                         help=f"folder for the Markdown report (default: {DEFAULT_REPORT_DIR})")
    p_audit.set_defaults(func=cmd_audit)

    p_verify = sub.add_parser("verify", help="check basic network health and OSPF status")
    p_verify.add_argument("--inventory", default=DEFAULT_INVENTORY, help=inventory_help)
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        return 2
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
