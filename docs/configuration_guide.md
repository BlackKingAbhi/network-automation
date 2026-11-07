# Cisco Device Configuration Guide

The files in `configurations/` are **sanitized, lab-ready sample configurations** written for Cisco IOSv (routers) and IOSvL2 (switches). They have **not** been verified on physical hardware. Read every file before you apply it.

## 1. Build the lab

1. In GNS3 / EVE-NG / CML add 2 x IOSv routers (R1, R2), 2 x IOSvL2 switches (SW1, SW2) and 2 VPCS hosts (PC1, PC2).
2. Cable them as in [network_topology.md](network_topology.md).
3. Connect every device's **Gi0/3** to a management switch / Cloud node that is bridged to your PC's host-only adapter.
4. Give your PC's host-only adapter an IP in the management subnet (example `192.168.150.50/24`).

## 2. Prepare the configuration files

Open each `.cfg` file and:

1. Replace `CHANGE_ME_ENABLE_SECRET` and `CHANGE_ME_ADMIN_PASSWORD` with your own lab passwords.
2. If your management subnet is not 192.168.150.0/24, replace the management IPs, the `ip default-gateway`, the `MGMT-SSH` ACL, the `ntp server` and the `logging host` addresses.
3. **Do not commit the edited files** with real passwords. Keep your edited copies outside the public repository.

## 3. Apply the configuration

On the device console:

```
Router> enable
Router# configure terminal
Router(config)# ! paste the contents of R1.cfg here
Router(config)# end
R1# copy running-config startup-config
```

Lines starting with `!` are comments and are ignored by IOS.

Notes:
- `crypto key generate rsa general-keys modulus 2048` creates the SSH keys. It must run **before** `ip ssh version 2`. It runs once and does not appear in `show running-config`. If keys already exist IOS asks whether to replace them - answer `no`.
- If your IOS image does not support `algorithm-type scrypt`, use `enable secret <password>` and `username netadmin privilege 15 secret <password>` instead.
- If IOS rejects `line vty 5 15`, your image has only 5 VTY lines - remove that block.

## 4. What each configuration section does

| Section | Commands | Purpose |
|---------|----------|---------|
| Hostname | `hostname R1` | Device name shown in the prompt and used by netauto |
| Password protection | `enable algorithm-type scrypt secret`, `service password-encryption` | Strong hashed enable password; type-7 obfuscation for other passwords |
| Local user | `username netadmin privilege 15 ... secret ...` | Account used for SSH; privilege 15 = enable mode after login |
| SSH | `ip domain-name`, `crypto key generate rsa`, `ip ssh version 2` | Encrypted remote access, SSHv2 only |
| Brute-force protection | `login block-for 120 attempts 3 within 60` | Blocks logins after repeated failures |
| VTY lines | `transport input ssh`, `login local`, `access-class MGMT-SSH in`, `exec-timeout 10 0` | SSH only, local users, only from the management subnet, idle timeout |
| Services | `no ip http server`, `no ip http secure-server` | Disable the unused web interface |
| Time & logs | `ntp server`, `logging host`, `service timestamps` | Correct timestamps and central log storage |
| Banner | `banner motd` | Legal warning message |
| OSPF (routers) | `router ospf 1`, `network ... area 0`, `passive-interface default` | Dynamic routing between R1 and R2 |
| Router-on-a-stick (R1) | `interface Gi0/1.10`, `encapsulation dot1Q 10` | Inter-VLAN routing for VLAN 10 and 20 |
| VLANs (switches) | `vlan 10`, `vlan 20`, `vlan 99`, `vlan 999` | Layer 2 segmentation |
| Trunks | `switchport mode trunk`, `native vlan 999`, `allowed vlan 10,20`, `nonegotiate` | Carry VLANs, unused native VLAN, no DTP |
| Access ports | `switchport mode access`, `portfast edge`, `bpduguard enable` | End-device ports, protect against rogue switches |
| Unused ports | `shutdown`, `switchport access vlan 999` | Reduce attack surface |

## 5. Verify the lab manually (before running netauto)

| Command | Expected result |
|---------|-----------------|
| `show ip interface brief` | Used interfaces are `up/up`, unused ones `administratively down` |
| `show vlan brief` (switches) | VLAN 10, 20, 99, 999 exist; SW2 Gi0/1 in VLAN 10, Gi0/2 in VLAN 20 |
| `show interfaces trunk` (switches) | Gi0/0 (and Gi0/1 on SW1) trunking, native 999, allowed 10,20 |
| `show ip ospf neighbor` (routers) | Neighbour in `FULL/  -` state |
| `show ip route ospf` (R1) | Routes to 2.2.2.2 and 172.16.2.0/24 |
| `show ip ssh` | `SSH Enabled - version 2.0` |
| From PC1: `ping 10.10.20.10` | Inter-VLAN routing via R1 works |
| From your PC: `ssh netadmin@192.168.150.101` | SSH login works |

Configure the VPCS hosts, e.g. `PC1> ip 10.10.10.10/24 10.10.10.1` and `PC2> ip 10.10.20.10/24 10.10.20.1`.

## 6. Run netauto

```bash
netauto check
netauto backup --commit
netauto audit
netauto verify
```

## 7. Try a "bad change" to see the tools work

On R2, introduce a security problem and an OSPF problem:

```
R2(config)# line vty 0 4
R2(config-line)# transport input telnet ssh
R2(config-line)# exit
R2(config)# interface GigabitEthernet0/0
R2(config-if)# shutdown
```

Then run `netauto backup --commit`, `netauto audit` (Telnet FAIL on R2) and `netauto verify` (R1 has no OSPF neighbour). `git -C <backup-repo> diff HEAD~1` shows exactly what changed. Undo the change afterwards.
