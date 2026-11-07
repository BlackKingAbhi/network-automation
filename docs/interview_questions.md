# Interview Preparation - Questions and Answers

Simple answers you can explain in your own words. Questions 1-10 are general networking; 11-30 relate directly to this project.

---

## Networking Fundamentals

**1. What is the difference between the OSI and TCP/IP models?**
The OSI model has 7 layers (Physical, Data Link, Network, Transport, Session, Presentation, Application) and is used for teaching and troubleshooting. TCP/IP has 4 layers (Network Access, Internet, Transport, Application) and is what the Internet actually uses. Switches work mainly at Layer 2, routers at Layer 3.

**2. What is the difference between TCP and UDP?**
TCP is connection-oriented and reliable (three-way handshake, acknowledgements, retransmission) - used by SSH (port 22), HTTP/HTTPS. UDP is connectionless and faster but unreliable - used by DNS queries, NTP (port 123) and syslog (port 514).

**3. What is a subnet mask? How many usable hosts does a /30 have?**
A subnet mask divides an IP address into network and host parts. A /30 (255.255.255.252) has 4 addresses: 1 network, 1 broadcast, **2 usable hosts** - perfect for a point-to-point link like R1-R2 (10.0.12.1 and 10.0.12.2).

**4. What is the difference between a router and a switch?**
A switch forwards frames inside the same network using **MAC addresses** (Layer 2). A router forwards packets between different networks using **IP addresses** and a routing table (Layer 3). In this project SW1/SW2 connect devices in VLANs, and R1/R2 route between networks.

**5. What is ARP?**
Address Resolution Protocol finds the MAC address that belongs to an IP address on the local network, using a broadcast request and a unicast reply.

## VLANs and Switching

**6. What is a VLAN and why use it?**
A VLAN splits one physical switch into several logical networks (separate broadcast domains). Benefits: security (users separated from servers), smaller broadcast domains, and easier management. This lab uses VLAN 10 (USERS) and VLAN 20 (SERVERS).

**7. What is the difference between an access port and a trunk port?**
An access port belongs to one VLAN and connects end devices (PC1 on SW2 Gi0/1). A trunk carries multiple VLANs between switches/routers, adding an **802.1Q tag** to each frame (SW1-SW2, R1-SW1).

**8. What is the native VLAN and why change it to an unused VLAN?**
The native VLAN carries untagged frames on a trunk (VLAN 1 by default). Changing it to an unused VLAN (999 here) protects against **VLAN hopping** (double-tagging) attacks. Both ends of the trunk must use the same native VLAN.

**9. How do devices in different VLANs communicate?**
Through a Layer 3 device. This lab uses **router-on-a-stick**: R1 has sub-interfaces Gi0/1.10 and Gi0/1.20 with `encapsulation dot1Q`, acting as the default gateway for each VLAN.

**10. What are PortFast and BPDU Guard?**
PortFast puts an access port into forwarding immediately, skipping the STP listening/learning states - used only on end-device ports. BPDU Guard shuts down a PortFast port if it receives a BPDU, which stops someone from connecting an unauthorised switch.

## Routing and OSPF

**11. What is OSPF?**
Open Shortest Path First is a **link-state** interior gateway routing protocol. Routers exchange link-state information, build the same map of the network, and use Dijkstra's SPF algorithm to choose the lowest-**cost** path. It's an open standard, its administrative distance is 110, and it converges quickly.

**12. What are the OSPF neighbour states?**
Down → Init → 2-Way → ExStart → Exchange → Loading → **Full**. FULL means the databases are synchronised. On broadcast networks DROTHER routers stay in 2-Way with each other, which is normal. `netauto verify` flags neighbours that are not FULL.

**13. What must match for two routers to become OSPF neighbours?**
Same area, same subnet and mask, same hello/dead timers, same authentication, compatible network type and MTU, and unique router IDs.

**14. Why did you use `passive-interface default`?**
It stops OSPF hellos from being sent on all interfaces, so no one can form a neighbour on a user VLAN. Only the WAN interface is made active with `no passive-interface Gi0/0`. The networks are still advertised.

**15. What is a router ID and how is it chosen?**
A 32-bit unique identifier for an OSPF router. Order: manually configured `router-id` → highest loopback IP → highest active interface IP. I set it manually (1.1.1.1 / 2.2.2.2) so it never changes.

## SSH, Telnet and Device Security

**16. Why SSH instead of Telnet?**
Telnet (TCP 23) sends everything, including usernames and passwords, in **clear text**; anyone capturing traffic can read them. SSH (TCP 22) encrypts the whole session. SSH version 1 has known weaknesses, so we force **version 2**.

**17. What is needed to enable SSH on a Cisco device?**
`hostname`, `ip domain-name`, an RSA key (`crypto key generate rsa modulus 2048`), a local user (`username ... secret ...`), `ip ssh version 2`, and on the VTY lines `login local` and `transport input ssh`.

**18. What is the difference between `enable password` and `enable secret`?**
`enable password` is stored in clear text (or weak type 7 with password encryption, which is easily reversed). `enable secret` is stored as a one-way hash (type 5 MD5, or the stronger type 8/9). If both exist, `enable secret` is used. The audit fails if `enable password` exists.

**19. What does `service password-encryption` do and is it enough?**
It hides clear-text passwords in the config using type 7 encoding, protecting against "shoulder surfing". Type 7 is easily reversed, so it is not real encryption - strong secrets should use `secret` (hashing). It's still a basic best practice.

**20. Why are NTP and remote syslog security requirements?**
Without correct time (NTP), log timestamps are wrong and you cannot correlate events during an incident. Remote syslog keeps a copy of the logs off the device, so an attacker who gains access cannot simply erase them, and logs survive a reboot.

**21. What other hardening did you apply on the VTY lines?**
`access-class MGMT-SSH in` (only the management subnet can connect), `exec-timeout 10 0` (idle sessions closed), and `login block-for` to slow down brute-force attempts.

## Python, Netmiko and Automation

**22. What is Netmiko and why did you use it?**
Netmiko is a Python library built on **Paramiko** (SSH) that simplifies connecting to network devices. It handles login, prompts, paging (`terminal length 0`) and enable mode. `send_command()` returns the command output as a string. It's simple and widely used - good for beginners.

**23. How does your tool handle connection errors?**
`connect_to_device` catches `NetmikoTimeoutException` (unreachable / no SSH) and `NetmikoAuthenticationException` (wrong credentials) and raises one friendly `DeviceConnectionError`. The backup and verify loops catch it, report the device as failed, and **continue with the other devices**.

**24. How do you keep credentials secure?**
No passwords in the code, inventory or Git. The tool reads them from environment variables or prompts with `getpass` (hidden input). `.env` files and backups are in `.gitignore`, and only a `.env.example` without secrets is published.

**25. Why YAML for the inventory and policy?**
YAML is human-readable, easy to edit and supports lists and dictionaries. Separating data (devices, rules) from code means you can add a device or change a severity without touching Python. I use `yaml.safe_load` so the file cannot execute code.

**26. How does the security audit work?**
It reads each saved `.cfg` file and runs six small functions that use string and regex checks (for example `^ip ssh version 2`). For Telnet it splits the config into `line vty` blocks and checks `transport input`. Every check returns PASS or FAIL with a detail, and the results go into a Markdown report sorted by severity.

**27. Why audit the saved backups instead of the live device?**
The audit works offline and quickly, and it doesn't need device access. The same backups are version-controlled, so you can also audit an old configuration. It also keeps "collecting" and "analysing" as separate, simpler steps.

## Git and Configuration Backup

**28. Why use Git for configuration backups?**
Git keeps a history of every version. `git diff` shows exactly what line changed between two backups, and `git log` shows when. This helps with troubleshooting ("what changed before the outage?"), auditing, and restoring an older configuration manually.

**29. Why are the backups in a separate private repository?**
Backups contain password hashes, IP addresses and the network design - sensitive information. The public GitHub repo contains only code and **sanitized** samples. The `.gitignore` excludes `backups/*` and `reports/*`.

**30. Why do you remove some lines before saving a backup?**
Lines like `Current configuration : 4021 bytes`, `! Last configuration change at ...` and `ntp clock-period` change even when nobody changed the config. Removing them means Git only records real changes.

## Testing

**31. How did you test without real Cisco devices?**
With **pytest** and **mocking**. In the backup tests I replace `connect_to_device` with a fake that returns a `MagicMock` connection whose `send_command` returns a sample running-config. The tests check that the file is saved correctly, that volatile lines are removed, and that authentication errors are handled. Audit and verify tests use sample configuration and `show` command text. I also ran the CLI against a small local SSH simulator. The full lab run in GNS3/EVE-NG is the next step.

**32. What would you improve next?**
More audit rules (SNMP, unused ports, VTY ACL), parallel connections with threads for larger networks, scheduling backups automatically (cron / Task Scheduler), and testing on more IOS versions.

---

### Tips for explaining the project in an interview
1. Start with the **problem**: manual backups and security checks are slow and error-prone.
2. Explain the **four commands** and show the topology diagram.
3. Mention **security**: SSH only, no credentials in code, private backup repo.
4. Be honest about the scope: "It's a learning project. I tested it with unit tests and a simulator, and I'm validating it in GNS3."
