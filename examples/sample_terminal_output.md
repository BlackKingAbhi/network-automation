# Sample Terminal Output

> **How this output was produced:** the commands below were executed for real
> with `netauto`, but against a **local SSH simulator** (a small Python/Paramiko
> program that imitates Cisco IOS prompts and replies with the sample configs and
> sample `show` outputs). It was **not** captured from real Cisco devices.
> That is why every host shows `127.0.0.1`. In your lab you will see the
> 192.168.150.x management addresses. SW2 Gi0/2 was deliberately simulated as
> DOWN to show how problems are reported.

```text
$ netauto check

Checking SSH connectivity to 4 device(s)...

  [OK]   R1    127.0.0.1         hostname: R1
  [OK]   R2    127.0.0.1         hostname: R2
  [OK]   SW1   127.0.0.1         hostname: SW1
  [OK]   SW2   127.0.0.1         hostname: SW2

4/4 device(s) reachable via SSH.

$ netauto backup --commit

Backing up 4 device(s) to 'backups'...

[*] Backing up R1 (127.0.0.1) ...
    [OK]   saved to backups/R1.cfg
[*] Backing up R2 (127.0.0.1) ...
    [OK]   saved to backups/R2.cfg
[*] Backing up SW1 (127.0.0.1) ...
    [OK]   saved to backups/SW1.cfg
[*] Backing up SW2 (127.0.0.1) ...
    [OK]   saved to backups/SW2.cfg

========== Backup Summary ==========
Successful : 4  R1, R2, SW1, SW2
Failed     : 0  
====================================
[OK] Committed backups to private Git repo: 'Config backup 2026-11-07 14:21:49'

$ netauto verify

==================== R1 (router) ====================
  Interfaces:
    Interface               IP Address        Status                  Protocol
    GigabitEthernet0/0      10.0.12.1         up                      up
    GigabitEthernet0/1      unassigned        up                      up
    GigabitEthernet0/1.10   10.10.10.1        up                      up
    GigabitEthernet0/1.20   10.10.20.1        up                      up
    GigabitEthernet0/2      unassigned        administratively down   down
    GigabitEthernet0/3      192.168.150.101   up                      up
    Loopback0               1.1.1.1           up                      up

  Routing table (9 routes):
    C        1.1.1.1 is directly connected, Loopback0
    O        2.2.2.2 [110/2] via 10.0.12.2, 00:12:40, GigabitEthernet0/0
    C        10.0.12.0/30 is directly connected, GigabitEthernet0/0
    L        10.0.12.1/32 is directly connected, GigabitEthernet0/0
    C        10.10.10.0/24 is directly connected, GigabitEthernet0/1.10
    L        10.10.10.1/32 is directly connected, GigabitEthernet0/1.10
    C        10.10.20.0/24 is directly connected, GigabitEthernet0/1.20
    L        10.10.20.1/32 is directly connected, GigabitEthernet0/1.20
    O        172.16.2.0 [110/2] via 10.0.12.2, 00:12:40, GigabitEthernet0/0

  OSPF neighbours:
    2.2.2.2         FULL      10.0.12.2       GigabitEthernet0/0

  Health:
    [OK] No problems found

==================== R2 (router) ====================
  Interfaces:
    Interface               IP Address        Status                  Protocol
    GigabitEthernet0/0      10.0.12.2         up                      up
    GigabitEthernet0/1      unassigned        administratively down   down
    GigabitEthernet0/2      unassigned        administratively down   down
    GigabitEthernet0/3      192.168.150.102   up                      up
    Loopback0               2.2.2.2           up                      up
    Loopback1               172.16.2.1        up                      up

  Routing table (8 routes):
    O        1.1.1.1 [110/2] via 10.0.12.1, 00:12:41, GigabitEthernet0/0
    C        2.2.2.2 is directly connected, Loopback0
    C        10.0.12.0/30 is directly connected, GigabitEthernet0/0
    L        10.0.12.2/32 is directly connected, GigabitEthernet0/0
    O        10.10.10.0/24 [110/2] via 10.0.12.1, 00:12:41, GigabitEthernet0/0
    O        10.10.20.0/24 [110/2] via 10.0.12.1, 00:12:41, GigabitEthernet0/0
    C        172.16.2.0/24 is directly connected, Loopback1
    L        172.16.2.1/32 is directly connected, Loopback1

  OSPF neighbours:
    1.1.1.1         FULL      10.0.12.1       GigabitEthernet0/0

  Health:
    [OK] No problems found

==================== SW1 (switch) ====================
  Interfaces:
    Interface               IP Address        Status                  Protocol
    GigabitEthernet0/0      unassigned        up                      up
    GigabitEthernet0/1      unassigned        up                      up
    GigabitEthernet0/2      unassigned        administratively down   down
    GigabitEthernet0/3      unassigned        up                      up
    Vlan1                   unassigned        administratively down   down
    Vlan99                  192.168.150.111   up                      up

  Health:
    [OK] No problems found

==================== SW2 (switch) ====================
  Interfaces:
    Interface               IP Address        Status                  Protocol
    GigabitEthernet0/0      unassigned        up                      up
    GigabitEthernet0/1      unassigned        up                      up
    GigabitEthernet0/2      unassigned        down                    down
    GigabitEthernet0/3      unassigned        up                      up
    Vlan1                   unassigned        administratively down   down
    Vlan99                  192.168.150.112   up                      up

  Health:
    [WARN] Interface GigabitEthernet0/2 is down/down

========== Verification Summary ==========
Healthy devices      : 3/4
  SW2: 1 problem(s)
==========================================

$ netauto audit

Auditing 4 configuration file(s) from 'backups'

=== R1 ===
  [PASS] [HIGH  ] SSH version 2 must be configured
  [PASS] [HIGH  ] Telnet must not be enabled on VTY lines
  [PASS] [HIGH  ] Weak enable password must not be configured
  [PASS] [MEDIUM] Remote logging (syslog) must be configured
  [PASS] [MEDIUM] Password encryption service must be enabled
  [PASS] [LOW   ] NTP server must be configured

=== R2 ===
  [PASS] [HIGH  ] SSH version 2 must be configured
  [PASS] [HIGH  ] Telnet must not be enabled on VTY lines
  [PASS] [HIGH  ] Weak enable password must not be configured
  [PASS] [MEDIUM] Remote logging (syslog) must be configured
  [PASS] [MEDIUM] Password encryption service must be enabled
  [PASS] [LOW   ] NTP server must be configured

=== SW1 ===
  [PASS] [HIGH  ] SSH version 2 must be configured
  [PASS] [HIGH  ] Telnet must not be enabled on VTY lines
  [PASS] [HIGH  ] Weak enable password must not be configured
  [PASS] [MEDIUM] Remote logging (syslog) must be configured
  [PASS] [MEDIUM] Password encryption service must be enabled
  [PASS] [LOW   ] NTP server must be configured

=== SW2 ===
  [PASS] [HIGH  ] SSH version 2 must be configured
  [PASS] [HIGH  ] Telnet must not be enabled on VTY lines
  [PASS] [HIGH  ] Weak enable password must not be configured
  [PASS] [MEDIUM] Remote logging (syslog) must be configured
  [PASS] [MEDIUM] Password encryption service must be enabled
  [PASS] [LOW   ] NTP server must be configured

Audit complete: 24/24 checks passed, 0 failed.
Markdown report written to: reports/security_audit_report.md
```
