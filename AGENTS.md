# AGENTS.md

Project instructions for AI coding agents working in this repository.

## Project

Ansible playbooks for managing Linux hosts on AWS and Cisco IOS routers.

- Control node: Ubuntu Linux machine with `ansible-core` installed system-wide (tested with 2.21.x).
- Control node access from the dev machine: SSH to `master@192.168.1.151` (password in the local `.secret` file under the `host_pass` key; on Windows use `plink`). Only read-only diagnostics are allowed remotely, and only after explicit user approval. Never print passwords.
- Control node Python environment: `ansible` is installed system-wide via `apt` and a virtualenv does NOT contain it (the shell falls through to `/usr/bin/ansible`). Install Python dependencies with `apt` (for example `python3-winrm`); plain `pip install` fails with `externally-managed-environment` (PEP 668).
- Managed Windows host (optional, `windows` inventory group): WinRM over plain HTTP on TCP port 5985 with NTLM transport. The connection plugin is the one built into ansible-core (`ansible_connection=winrm`); since ansible-core 2.20 `ansible.windows.winrm` no longer exists. The password is read from the `windows_pass` environment variable by `group_vars/windows.yml`.
- Managed Cisco IOS routers (optional, `routers` inventory group): SSH on TCP port 22 using `ansible.netcommon.network_cli` and `cisco.ios.ios`. The password is read from the `routers_pass` environment variable by `group_vars/routers.yml`.
- Inventory: dynamic. `./dynamic_inventory.py` (configured in `ansible.cfg`) fetches hosts and groups from the local Django IPAM API at `http://127.0.0.1:8000/api/ansible/inventory/`. The API runs in Docker (`ipam/docker-compose.yml`) with SQLite storage. Manage hosts through the Django Admin at `http://127.0.0.1:8000/admin/` or the REST API under `/api/`. The static `hosts` file no longer exists.
- Playbooks: `site.yml` targets `webservers`; `router_hostname.yml` and `router_interfaces.yml` target Cisco IOS routers.
- Roles: `roles/<name>/`.
- Router hostname role: `roles/router_hostname/` derives the default IOS hostname from the inventory alias (for example, `rtr1.lab` becomes `rtr1`) and saves changes to startup configuration.
- Group variables: `group_vars/<group>.yml` (still static files; loaded automatically next to the inventory script).
- WordPress role: `roles/wordpress/` deploys Apache, MariaDB, PHP, WordPress, and HTTPS to Ubuntu Server 24.04.
- Collection dependencies: `requirements.yml` (`ansible.mysql`, `ansible.windows`, `ansible.netcommon`, and `cisco.ios`). Install them on the control node with `ansible-galaxy collection install -r requirements.yml`.
- Python dependencies: `requirements.txt` (currently `pywinrm`). Install them on the control node with `pip install -r requirements.txt` (use a venv or the distro package on PEP 668 systems).
- SSH key path (`ansible_ssh_private_key_file`) is stored per host in the IPAM database and must exist on the control node at `/etc/ansible/keys/`. The key is never committed (`/keys/*` is in `.gitignore`).
- IPAM web application: `ipam/` (Django + DRF + SQLite, Docker Compose). The container publishes `127.0.0.1:8000` only and has no API token; the inventory script talks to it over localhost.

## Language

- All code comments, documentation, commit messages, and PR descriptions are written in English.
- Conversation with the user is in English.

## Rules

1. Before any action that changes files, runs git commands, or runs `ansible-playbook` against hosts, show exactly what will be done and wait for explicit user approval.
2. Never push to `master`. Work in a feature branch and open a Pull Request.
3. Never commit secrets (SSH keys, `.pem`, passwords, tokens). Keep router credentials out of the repository; `routers_pass` is provided through the control node environment.
4. Do not change inventory variables or IPAM host data without explicit approval. Windows hosts belong to the `windows` group only; never add them to `webservers` (the WordPress roles target Ubuntu). Cisco IOS devices belong to `routers` and must not be targeted by the Linux/WordPress roles.
5. Store `wordpress_db_password` and `wordpress_admin_password` as Ansible Vault encrypted values in `group_vars/webservers.yml`. Keep the Vault password outside the repository. Never put plaintext credentials in role tasks, templates, documentation, or command-line arguments.
6. When `wordpress_https_enabled` is `true`, the WordPress role requires a configured domain and email addresses, DNS pointing to the target host, and network access to ports 80 and 443 for Let's Encrypt. When it is `false`, the site is served over plain HTTP and no certificate is requested.
7. Interact with GitHub through the `github` MCP server (configured globally in OpenCode, authenticated with a fine-grained PAT from the `GITHUB_MCP_PAT` environment variable). Do not use the `gh` CLI. The token file `.secret` is gitignored and must never be committed or printed.

## Commands

Run from the repository root on the control node:

```bash
docker compose -f ipam/docker-compose.yml ps     # IPAM stack must be up for inventory
ansible-inventory --list
ansible-playbook site.yml --syntax-check
ansible-playbook site.yml --check --diff
ansible-playbook site.yml
ansible-playbook router_hostname.yml --syntax-check
ansible-playbook router_hostname.yml --check --diff
ansible-playbook router_hostname.yml
ansible-playbook router_hostname.yml --limit rtr1.lab
ansible-playbook router_interfaces.yml --syntax-check
ansible-playbook router_interfaces.yml
ansible webservers -m ping
ansible routers -m cisco.ios.ios_facts
```

Order: syntax check, then dry run, then real run (only after approval).
Syntax checks are local. Ping, IOS facts, dry-runs, and real runs contact managed hosts and require approval before execution. Review the router hostname dry-run and obtain separate approval before applying it. `site.yml` targets only `webservers`; use `router_hostname.yml --limit <router>` to configure one router.

## Conventions

See the skills in `.opencode/skills/`:

- `ansible-playbook-conventions`: writing playbooks and roles.
- `ansible-run-playbook`: running and verifying playbooks.
- `git-pr-workflow`: branches, commits, and pull requests (PRs are created via the GitHub MCP server).

When editing the WordPress role, preserve idempotency, use fully qualified Ansible module names, manage MariaDB with `ansible.mysql`, and pass WP-CLI passwords through standard input with secret-bearing tasks marked `no_log: true`.
