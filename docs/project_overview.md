# Project Overview

## In one sentence

A Python tool that logs in to Cisco routers and switches over SSH, backs up their configurations into a private Git repository, checks them for basic security mistakes, and verifies that interfaces and OSPF are healthy.

## Why I built this project

Network engineers repeat the same tasks every day: take backups, check that security settings are correct, and confirm the network is healthy after a change. Doing this by hand on every device is slow and mistakes are easy to make. I wanted to learn how Python can automate these tasks safely, using the same tools that are common in real network teams: **Netmiko, YAML and Git**.

## What the project shows about my skills

| Area | Where it appears in the project |
|------|--------------------------------|
| Networking fundamentals | IP plan, subnets, management network, `show` commands |
| Cisco IOS | Four complete device configurations (routers and switches) |
| Switching / VLANs | VLAN 10/20, 802.1Q trunks, native VLAN, access ports, PortFast, BPDU Guard |
| Routing | OSPF area 0 between R1 and R2, router-on-a-stick inter-VLAN routing |
| Network security | SSHv2 only, no Telnet, enable secret, password encryption, ACL on VTY, syslog, NTP |
| Python | Modules, functions, exceptions, file handling, regex, argparse CLI |
| Automation | Netmiko SSH sessions, inventory in YAML |
| Version control | Git history of configuration changes |
| Testing | Pytest with mocked SSH connections |
| Secure coding | No hard-coded credentials, getpass, environment variables, .gitignore |

## The four commands

1. **`netauto check`** - "Can I log in to every device?"
2. **`netauto backup`** - "Save a copy of every configuration (and commit it to Git)."
3. **`netauto audit`** - "Are the basic security rules followed?" (PASS/FAIL + Markdown report)
4. **`netauto verify`** - "Are interfaces up and OSPF neighbours FULL?"

## Design choices (and why)

- **Small and readable over feature-rich.** Each module is one file with short functions.
- **Policy in YAML.** Severity and the list of checks can be changed without editing Python.
- **Backups in a separate private Git repo.** Configurations contain password hashes and network details, so they are never part of the public code repository.
- **Volatile lines are removed from backups** so that `git diff` only shows real changes.
- **Tests do not need devices.** The Netmiko connection is replaced with a mock object.

## Honest scope statement

The Python code was tested with unit tests and against a local SSH simulator. The Cisco configurations are written for IOSv/IOSvL2 and are "lab-ready", but the full workflow still needs to be run in a real virtual lab (GNS3, EVE-NG or Cisco CML). See the README section *Project Status*.
