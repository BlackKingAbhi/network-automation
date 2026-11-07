# How It Works

This page explains the code module by module, in the order the data flows.

```
inventory/devices.yaml --> connection.py --SSH--> Cisco device
                                |
            +-------------------+-------------------+
            v                                       v
       backup.py                               verify.py
   show running-config                 show ip interface brief
   clean -> R1.cfg ...                 show ip route / ospf neighbor
   git commit (private repo)           parse -> find problems -> print
            |
            v
        audit.py  <-- policies/security_policy.yaml
   regex checks -> PASS/FAIL -> reports/security_audit_report.md
```

## 1. `main.py` - the command-line interface

- Uses Python's built-in **argparse** to create four sub-commands: `check`, `backup`, `audit`, `verify`.
- Each sub-command is connected to a small handler function (`cmd_check`, `cmd_backup`, ...).
- Each handler returns an **exit code** (0 = success, 1 = something failed). This lets the tool be used in scripts.
- `pyproject.toml` maps the command `netauto` to `netauto.main:main`.

## 2. `connection.py` - inventory, credentials, SSH

**`load_inventory(path)`** reads the YAML file with `yaml.safe_load` (safe_load never runs code from the file) and checks every device has a `name` and `host`.

**`get_credentials()`** gets the username, password and enable secret:
1. from environment variables `NETAUTO_USERNAME`, `NETAUTO_PASSWORD`, `NETAUTO_ENABLE_SECRET`, or
2. by asking the user. `getpass.getpass()` hides the password while typing.

The credentials only live in memory - they are never written to disk or printed.

**`connect_to_device(device, credentials)`** calls Netmiko's `ConnectHandler(...)`. Netmiko opens the SSH session, logs in, disables paging (`terminal length 0`) and finds the prompt. Errors are converted into one friendly exception type, `DeviceConnectionError`:

| Netmiko exception | Message shown |
|-------------------|---------------|
| `NetmikoTimeoutException` | connection timed out - check IP / reachability / SSH |
| `NetmikoAuthenticationException` | authentication failed - check username and password |
| anything else | the original error text |

If the prompt ends in `>` (user mode), it runs `enable` using the enable secret.

## 3. `backup.py` - configuration backup

For every device:
1. Connect (`connect_to_device`).
2. `send_command("show running-config")`.
3. **Sanity check** - if the output does not contain `hostname`, it is probably an error message, so nothing is saved.
4. **`clean_config()`** removes lines that change on every run even when the configuration did not change:
   - `Building configuration...`
   - `Current configuration : 4021 bytes`
   - `! Last configuration change at ...` / `! NVRAM config last updated at ...`
   - `ntp clock-period ...`
   Without this, Git would report a "change" after every backup.
5. Save as `<backup_dir>/<name>.cfg`, e.g. `backups/R1.cfg`.
6. Always `disconnect()` (in a `finally:` block), even if the command failed.

A failure on one device does not stop the others. A summary shows which devices succeeded.

**`commit_backups(backup_dir)`** (only with `--commit`):
1. Checks that `backup_dir` contains a `.git` folder (it must be a separate private repo).
2. `git add --all`
3. `git diff --cached --quiet` - if nothing changed, skip (no empty commits).
4. `git commit -m "Config backup <date time>"`

Git is called with Python's `subprocess` module; no extra Git library is needed.

## 4. `audit.py` - security audit

1. **`load_policy()`** reads `policies/security_policy.yaml`. Each check has an `id`, `name`, `severity`, `enabled` and `remediation`.
2. **`CHECK_FUNCTIONS`** is a dictionary that maps each `id` to a small Python function.
3. **`audit_directory()`** reads every `*.cfg` file and runs every enabled check.

How each check decides PASS/FAIL:

| Check | Logic |
|-------|-------|
| `ssh_version_2` | a line exactly `ip ssh version 2` exists |
| `no_telnet` | split the config into `line vty` blocks. FAIL if a block has `transport input` containing `telnet` or `all`, **or has no `transport input` at all** (the IOS default may allow Telnet) |
| `no_weak_enable_password` | FAIL if `enable password` exists or if there is no `enable secret` |
| `ntp_server` | at least one `ntp server <ip>` |
| `remote_logging` | at least one `logging host <ip>` (or old style `logging <ip>`) |
| `password_encryption` | `service password-encryption` present and not `no service password-encryption` |

`^` in the regular expressions means "start of line" (with `re.MULTILINE`), so a comment or a description containing the same words does not cause a false PASS.

4. **`print_audit_results()`** prints `[PASS]`/`[FAIL]` with the severity.
5. **`generate_markdown_report()`** builds a report with a summary table, detailed results per device, and a list of findings sorted HIGH → MEDIUM → LOW with the fix command.

## 5. `verify.py` - network verification

Commands run:
- all devices: `show ip interface brief`
- routers only (`role: router`): `show ip route`, `show ip ospf neighbor`

Parsing with simple string handling:

```
GigabitEthernet0/2  unassigned  YES NVRAM  administratively down  down
parts[0]            parts[1]               parts[4:-1] = status    parts[-1] = protocol
```

The status can be two words ("administratively down"), so it is taken as everything between column 5 and the last column.

OSPF neighbour lines start with an IP address; the state column `FULL/  -` or `FULL/DR` is cut at `/` to get `FULL`.

Problems reported:
- interface status or protocol `down` (interfaces that are `administratively down` are ignored because they were shut down on purpose),
- OSPF neighbour not `FULL`,
- router with no OSPF neighbours,
- device not reachable over SSH.

Note: on broadcast networks (no `ip ospf network point-to-point`), two DROTHER routers normally stay in `2WAY`. In this lab the WAN link is point-to-point, so `FULL` is expected.

## 6. Tests (`tests/`)

- `test_audit.py` - builds a compliant config string, removes or changes one line, and checks that the right rule fails. Also checks the four sample configs pass and the insecure example fails.
- `test_backup.py` - replaces `connect_to_device` with a fake function that returns a `MagicMock` connection. The mock returns a fake `show running-config`, so the test can check the saved file without a device. Also tests authentication failure and the Git commit function in a temporary repo.
- `test_verify.py` - feeds sample `show` outputs to the parsers.

`monkeypatch` (pytest) temporarily replaces a function during one test; `tmp_path` gives each test an empty temporary folder.

## 7. Security measures in the code

- No credentials in code, inventory or Git; `getpass` hides typing.
- `.env`, `backups/*`, `reports/*` are in `.gitignore`.
- Backups go to a separate private Git repository.
- `yaml.safe_load` instead of `yaml.load`.
- Only read-only `show` commands are sent to devices - the tool never changes device configuration.
