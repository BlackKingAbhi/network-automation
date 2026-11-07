"""
verify.py - Basic network health verification.

Runs these Cisco IOS commands on each device:
    show ip interface brief   (all devices)
    show ip route             (routers only)
    show ip ospf neighbor     (routers only)

and reports simple problems:
    * interfaces that are DOWN (but not administratively shut down)
    * OSPF neighbours that are not in the FULL state
    * routers that have no OSPF neighbours at all
    * devices that cannot be reached over SSH

Parsing is done with simple string splitting and regular expressions so
that a beginner can read and understand every line.
"""

import re

from netauto.connection import DeviceConnectionError, connect_to_device, get_hostname

IPV4 = r"\d{1,3}(?:\.\d{1,3}){3}"


# ---------------------------------------------------------------------------
# Parsers (pure functions - easy to unit test without a device)
# ---------------------------------------------------------------------------
def parse_interface_brief(output):
    """
    Parse 'show ip interface brief'.

    Example line:
      GigabitEthernet0/0  10.0.12.1  YES NVRAM  up                    up
      GigabitEthernet0/2  unassigned YES NVRAM  administratively down down
    Returns a list of dicts: interface, ip, status, protocol
    """
    interfaces = []
    for line in output.splitlines():
        parts = line.split()
        # Skip the header line and anything that is too short.
        if len(parts) < 6 or parts[0] == "Interface":
            continue
        interfaces.append(
            {
                "interface": parts[0],
                "ip": parts[1],
                # Status can be two words: 'administratively down'
                "status": " ".join(parts[4:-1]),
                "protocol": parts[-1],
            }
        )
    return interfaces


def parse_ospf_neighbors(output):
    """
    Parse 'show ip ospf neighbor'.

    Example line:
      2.2.2.2   0   FULL/  -   00:00:33   10.0.12.2   GigabitEthernet0/0
    Returns a list of dicts: neighbor_id, state, address, interface
    """
    neighbors = []
    pattern = re.compile(rf"^({IPV4})\s+\d+\s+(\S+)")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        parts = line.split()
        neighbors.append(
            {
                "neighbor_id": match.group(1),
                "state": match.group(2).split("/")[0].upper(),  # 'FULL/DR' -> 'FULL'
                "address": parts[-2],
                "interface": parts[-1],
            }
        )
    return neighbors


def parse_routes(output):
    """
    Parse 'show ip route' into simple (code, prefix, line) entries.

    Example lines:
      C        10.0.12.0/30 is directly connected, GigabitEthernet0/0
      O        2.2.2.2 [110/2] via 10.0.12.2, 00:10:11, GigabitEthernet0/0
    """
    routes = []
    pattern = re.compile(rf"^([A-Za-z*]+(?: [A-Z0-9]{{1,2}})?)\s+({IPV4}(?:/\d+)?)")
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            routes.append(
                {"code": match.group(1).strip(), "prefix": match.group(2), "line": line.strip()}
            )
    return routes


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def find_problems(role, interfaces, neighbors):
    """Return a list of human-readable problems found in the parsed data."""
    problems = []
    for intf in interfaces:
        if intf["status"] == "administratively down":
            continue  # shut down on purpose - not a fault
        if intf["status"] != "up" or intf["protocol"] != "up":
            problems.append(
                f"Interface {intf['interface']} is {intf['status']}/{intf['protocol']}"
            )

    if role == "router":
        if not neighbors:
            problems.append("No OSPF neighbours found")
        for nbr in neighbors:
            if nbr["state"] != "FULL":
                problems.append(
                    f"OSPF neighbour {nbr['neighbor_id']} on {nbr['interface']} "
                    f"is {nbr['state']} (expected FULL)"
                )
    return problems


def analyze_outputs(hostname, role, outputs):
    """
    Turn raw command outputs into a structured result.

    outputs is a dict: {command: output_text}
    """
    interfaces = parse_interface_brief(outputs.get("show ip interface brief", ""))
    routes = parse_routes(outputs.get("show ip route", ""))
    neighbors = parse_ospf_neighbors(outputs.get("show ip ospf neighbor", ""))
    return {
        "hostname": hostname,
        "role": role,
        "reachable": True,
        "interfaces": interfaces,
        "routes": routes,
        "ospf_neighbors": neighbors,
        "problems": find_problems(role, interfaces, neighbors),
    }


def get_commands_for_role(role):
    """Switches in this lab are Layer 2 only, so they do not run OSPF."""
    commands = ["show ip interface brief"]
    if role == "router":
        commands += ["show ip route", "show ip ospf neighbor"]
    return commands


def verify_device(device, credentials, settings=None):
    """Connect to one device, run the commands and analyse the output."""
    try:
        connection = connect_to_device(device, credentials, settings)
    except DeviceConnectionError as error:
        return {
            "hostname": device["name"],
            "role": device.get("role", "router"),
            "reachable": False,
            "problems": [f"Device unreachable via SSH: {error}"],
        }

    try:
        hostname = get_hostname(connection)
        outputs = {
            cmd: connection.send_command(cmd)
            for cmd in get_commands_for_role(device.get("role", "router"))
        }
    finally:
        connection.disconnect()

    return analyze_outputs(hostname, device.get("role", "router"), outputs)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def print_verification(result):
    """Print the verification result of one device in a readable format."""
    print(f"\n==================== {result['hostname']} ({result['role']}) ====================")
    if not result["reachable"]:
        print(f"  [FAIL] {result['problems'][0]}")
        return

    print("  Interfaces:")
    print(f"    {'Interface':<24}{'IP Address':<18}{'Status':<24}{'Protocol'}")
    for intf in result["interfaces"]:
        print(
            f"    {intf['interface']:<24}{intf['ip']:<18}{intf['status']:<24}{intf['protocol']}"
        )

    if result["role"] == "router":
        print(f"\n  Routing table ({len(result['routes'])} routes):")
        for route in result["routes"]:
            print(f"    {route['line']}")

        print("\n  OSPF neighbours:")
        if not result["ospf_neighbors"]:
            print("    (none)")
        for nbr in result["ospf_neighbors"]:
            print(
                f"    {nbr['neighbor_id']:<16}{nbr['state']:<10}"
                f"{nbr['address']:<16}{nbr['interface']}"
            )

    print("\n  Health:")
    if result["problems"]:
        for problem in result["problems"]:
            print(f"    [WARN] {problem}")
    else:
        print("    [OK] No problems found")


def verify_all(devices, credentials, settings=None):
    """Verify every device and return the list of results."""
    results = []
    for device in devices:
        result = verify_device(device, credentials, settings)
        print_verification(result)
        results.append(result)
    return results
