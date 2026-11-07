# Installation Guide

## 1. Prerequisites

| Software | Version | Check with |
|----------|---------|-----------|
| Python | 3.8 or newer | `python --version` |
| Git | any recent version | `git --version` |
| A Cisco lab | GNS3, EVE-NG or Cisco CML with IOSv / IOSvL2 images | - |

On Windows 11, install **Python** from python.org (tick *"Add python.exe to PATH"*) and **Git for Windows** (it includes Git Bash). All commands below are for **Git Bash**; Linux/macOS differences are noted.

## 2. Get the project

```bash
cd ~/Desktop
unzip Network_Configuration_Backup_Security_Auditing_Project.zip
cd network-automation-project
```

## 3. Create a virtual environment

A virtual environment keeps the project's libraries separate from other Python projects.

```bash
python -m venv venv
source venv/Scripts/activate     # Git Bash on Windows
# source venv/bin/activate       # Linux / macOS
```

Your prompt now starts with `(venv)`.

## 4. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

- `requirements.txt` installs **Netmiko**, **PyYAML** and **Pytest**.
- `pip install -e .` creates the `netauto` command (it reads `pyproject.toml`).

Check it worked:

```bash
netauto --help
pytest -v
```

If `netauto` is not found, use `python -m netauto --help` instead - it does exactly the same thing.

## 5. Set up the inventory

Edit `inventory/devices.yaml` and change the `host` values to the management IPs of your lab devices. **Do not add usernames or passwords to this file.**

## 6. Provide credentials safely

Option A - be prompted (recommended):

```bash
netauto check
# SSH username: netadmin
# SSH password:            <- hidden while typing (getpass)
# Enable secret (press Enter to skip):
```

Option B - environment variables for the current terminal session only:

```bash
export NETAUTO_USERNAME=netadmin
read -s -p "Password: " NETAUTO_PASSWORD; export NETAUTO_PASSWORD; echo
export NETAUTO_ENABLE_SECRET=""     # empty = skip (user already has privilege 15)
```

Option C - an `.env` file (copied from `.env.example`). `.env` is in `.gitignore`, so it is never committed:

```bash
cp .env.example .env
nano .env          # or: notepad .env
source .env
```

## 7. Create the private backup repository

```bash
mkdir -p ~/netauto-config-backups
git -C ~/netauto-config-backups init
export NETAUTO_BACKUP_DIR=~/netauto-config-backups   # optional default for netauto
```

Now `netauto backup --commit` saves and commits there. **Never push this repository to a public site.**

## 8. Troubleshooting

| Problem | Likely cause / fix |
|---------|--------------------|
| `connection timed out` | Wrong IP, PC not in the management subnet, device Gi0/3 down, or SSH not configured. Try `ping` first. |
| `authentication failed` | Wrong username/password, or `login local` missing on the VTY lines. |
| `could not enter enable mode` | The user is not privilege 15 - set `NETAUTO_ENABLE_SECRET`. |
| SSH works in PuTTY but not in netauto | The VTY ACL `MGMT-SSH` may not include your PC's IP. |
| Old IOS refuses the SSH key exchange | Use a newer IOSv image, or update Netmiko/Paramiko. |
| `No .cfg files found in 'backups'` | Run `netauto backup` first, or use `--config-dir configurations`. |
