"""Unit tests for the parsers in netauto/verify.py using sample command output."""

from netauto import verify

SHOW_IP_INT_BRIEF = """\
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     10.0.12.1       YES NVRAM  up                    up
GigabitEthernet0/1     unassigned      YES NVRAM  up                    up
GigabitEthernet0/1.10  10.10.10.1      YES NVRAM  up                    up
GigabitEthernet0/2     unassigned      YES NVRAM  administratively down down
GigabitEthernet0/3     192.168.150.101 YES NVRAM  up                    down
Loopback0              1.1.1.1         YES NVRAM  up                    up
"""

SHOW_OSPF_NEIGHBOR_FULL = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2           0   FULL/  -        00:00:35    10.0.12.2       GigabitEthernet0/0
"""

SHOW_OSPF_NEIGHBOR_INIT = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2           1   INIT/DROTHER    00:00:38    10.0.12.2       GigabitEthernet0/0
"""

SHOW_IP_ROUTE = """\
Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       O - OSPF, IA - OSPF inter area

Gateway of last resort is not set

      1.0.0.0/32 is subnetted, 1 subnets
C        1.1.1.1 is directly connected, Loopback0
      2.0.0.0/32 is subnetted, 1 subnets
O        2.2.2.2 [110/2] via 10.0.12.2, 00:05:12, GigabitEthernet0/0
C        10.0.12.0/30 is directly connected, GigabitEthernet0/0
L        10.0.12.1/32 is directly connected, GigabitEthernet0/0
O IA     172.16.2.0/24 [110/2] via 10.0.12.2, 00:05:12, GigabitEthernet0/0
"""


def test_parse_interface_brief():
    interfaces = verify.parse_interface_brief(SHOW_IP_INT_BRIEF)
    assert len(interfaces) == 6
    gi02 = next(i for i in interfaces if i["interface"] == "GigabitEthernet0/2")
    assert gi02["status"] == "administratively down"
    assert gi02["protocol"] == "down"


def test_parse_ospf_neighbor_full():
    neighbors = verify.parse_ospf_neighbors(SHOW_OSPF_NEIGHBOR_FULL)
    assert neighbors == [
        {"neighbor_id": "2.2.2.2", "state": "FULL", "address": "10.0.12.2",
         "interface": "GigabitEthernet0/0"}
    ]


def test_parse_routes():
    routes = verify.parse_routes(SHOW_IP_ROUTE)
    codes = [r["code"] for r in routes]
    assert codes == ["C", "O", "C", "L", "O IA"]
    assert routes[1]["prefix"] == "2.2.2.2"


def test_problems_detected_for_down_interface_and_ospf_not_full():
    result = verify.analyze_outputs(
        "R1", "router",
        {
            "show ip interface brief": SHOW_IP_INT_BRIEF,
            "show ip route": SHOW_IP_ROUTE,
            "show ip ospf neighbor": SHOW_OSPF_NEIGHBOR_INIT,
        },
    )
    problems = " | ".join(result["problems"])
    assert "GigabitEthernet0/3 is up/down" in problems
    assert "INIT (expected FULL)" in problems
    # Administratively down interfaces are not reported as problems.
    assert "GigabitEthernet0/2" not in problems


def test_healthy_router_has_no_problems():
    healthy_brief = "\n".join(l for l in SHOW_IP_INT_BRIEF.splitlines() if "0/3" not in l)
    result = verify.analyze_outputs(
        "R1", "router",
        {"show ip interface brief": healthy_brief, "show ip ospf neighbor": SHOW_OSPF_NEIGHBOR_FULL},
    )
    assert result["problems"] == []


def test_switch_skips_ospf_checks():
    assert verify.get_commands_for_role("switch") == ["show ip interface brief"]
    result = verify.analyze_outputs("SW1", "switch", {"show ip interface brief": ""})
    assert result["problems"] == []  # no 'No OSPF neighbours' warning for switches
