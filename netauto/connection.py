"""
connection.py - Inventory loading, credential handling and SSH connections.

Responsibilities:
  1. Read the device inventory from a YAML file.
  2. Get login credentials SAFELY (environment variables or a hidden prompt).
     Credentials are never stored in source code or in the inventory file.
  3. Open an SSH connection to a Cisco IOS device using Netmiko and turn
     common failures (timeout, wrong password) into clear error messages.
"""

import getpass
import os

import yaml
from netmiko import (
    ConnectHandler,
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

# Names of the environment variables that may hold credentials.
ENV_USERNAME = "NETAUTO_USERNAME"
ENV_PASSWORD = "NETAUTO_PASSWORD"
ENV_ENABLE_SECRET = "NETAUTO_ENABLE_SECRET"


class DeviceConnectionError(Exception):
    """Raised when we cannot connect to a device (any reason)."""


def load_inventory(inventory_path):
    """
    Load the device inventory YAML file.

    Returns a tuple: (list_of_devices, settings_dict)
    Each device is a dict such as:
        {"name": "R1", "host": "192.168.150.101",
         "device_type": "cisco_ios", "role": "router"}
    """
    if not os.path.isfile(inventory_path):
        raise FileNotFoundError(f"Inventory file not found: {inventory_path}")

    with open(inventory_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    devices = data.get("devices", [])
    settings = data.get("settings", {}) or {}

    # Basic validation so the user gets a helpful message for typos.
    for device in devices:
        for required_key in ("name", "host"):
            if required_key not in device:
                raise ValueError(
                    f"Device entry {device} is missing the '{required_key}' key"
                )
        device.setdefault("device_type", "cisco_ios")
        device.setdefault("role", "router")

    return devices, settings


def get_credentials():
    """
    Return a dict with username, password and enable secret.

    Order of preference:
      1. Environment variables (NETAUTO_USERNAME, NETAUTO_PASSWORD,
         NETAUTO_ENABLE_SECRET)
      2. Interactive prompt. getpass hides the password while typing.
    """
    username = os.environ.get(ENV_USERNAME) or input("SSH username: ").strip()
    password = os.environ.get(ENV_PASSWORD) or getpass.getpass("SSH password: ")

    # The enable secret is optional. If the user account has privilege 15
    # the device is already in privileged (#) mode after login.
    secret = os.environ.get(ENV_ENABLE_SECRET)
    if secret is None:
        secret = getpass.getpass("Enable secret (press Enter to skip): ")

    return {"username": username, "password": password, "secret": secret}


def build_device_params(device, credentials, settings=None):
    """Build the dictionary that Netmiko's ConnectHandler expects."""
    settings = settings or {}
    params = {
        "device_type": device.get("device_type", "cisco_ios"),
        "host": device["host"],
        "username": credentials["username"],
        "password": credentials["password"],
        "port": device.get("port", settings.get("port", 22)),
        "conn_timeout": settings.get("timeout", 10),
    }
    if credentials.get("secret"):
        params["secret"] = credentials["secret"]
    return params


def connect_to_device(device, credentials, settings=None):
    """
    Open an SSH session to one device and enter privileged EXEC mode.

    Returns a Netmiko connection object.
    Raises DeviceConnectionError with a friendly message on failure.
    """
    params = build_device_params(device, credentials, settings)
    name = device["name"]

    try:
        connection = ConnectHandler(**params)
    except NetmikoTimeoutException:
        raise DeviceConnectionError(
            f"{name} ({device['host']}): connection timed out - "
            "check the IP address, reachability and that SSH is enabled"
        )
    except NetmikoAuthenticationException:
        raise DeviceConnectionError(
            f"{name} ({device['host']}): authentication failed - "
            "check the username and password"
        )
    except Exception as error:  # e.g. connection refused, SSH negotiation errors
        raise DeviceConnectionError(f"{name} ({device['host']}): {error}")

    # 'show running-config' needs privileged mode (prompt ending in '#').
    try:
        if not connection.check_enable_mode():
            connection.enable()
    except Exception:
        connection.disconnect()
        raise DeviceConnectionError(
            f"{name} ({device['host']}): could not enter enable mode - "
            "set NETAUTO_ENABLE_SECRET or give the user privilege 15"
        )

    return connection


def get_hostname(connection):
    """Return the device hostname from its prompt, e.g. 'R1#' -> 'R1'."""
    prompt = connection.find_prompt()
    return prompt.rstrip("#>").strip()
