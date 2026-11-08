#!/usr/bin/env python3
"""Ansible dynamic inventory backed by the Django IPAM API.

Queries GET /api/ansible/inventory/ on the local Django container and
prints the JSON Ansible expects. Uses only the Python standard library
so it runs under the system interpreter (PEP 668 safe).

Environment:
  IPAM_API_URL  base URL of the API (default: http://127.0.0.1:8000)
"""

import json
import os
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("IPAM_API_URL", "http://127.0.0.1:8000").rstrip("/")


def fetch_inventory():
    url = f"{API_URL}/api/ansible/inventory/"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def main():
    args = sys.argv[1:]
    try:
        inventory = fetch_inventory()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(
            f"dynamic_inventory: cannot reach IPAM API at {API_URL}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args or args[0] == "--list":
        print(json.dumps(inventory))
    elif args[0] == "--host":
        name = args[1] if len(args) > 1 else ""
        hostvars = inventory.get("_meta", {}).get("hostvars", {}).get(name, {})
        print(json.dumps(hostvars))
    else:
        print(f"dynamic_inventory: unsupported argument: {args[0]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
