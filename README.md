# HMP511 Ansible

Ansible playbooks for configuring Linux hosts on AWS and Cisco IOS routers, with a dynamic inventory served by a Django IPAM web application running in Docker.

## Requirements

- Control node: Ubuntu Linux with `ansible-core` installed system-wide (tested with 2.21.x). The control node is reachable for maintenance as `master@192.168.1.151`; its SSH password is stored locally in `.secret` under `host_pass` and is never committed.
- Docker Engine with the Compose plugin on the control node (runs the IPAM web application and API).
- Managed WordPress host: Ubuntu Server 24.04. Inbound TCP port 80 must be reachable from the internet; port 443 is additionally required when `wordpress_https_enabled` is `true`.
- Managed Windows host (optional, `windows` group): WinRM enabled on TCP port 5985, reachable from the control node, with the `pywinrm` package and the `ansible.windows` collection installed.
- Cisco IOS routers (optional, `routers` group): reachable from the control node over SSH on TCP port 22; keep the login password in the control node environment variable `routers_pass`.
- SSH private key `Stokholm.pem` at `/etc/ansible/keys/` on the control node (path stored per host in the IPAM database). The key is never committed.
- Passwordless `sudo` for the `ubuntu` user on each managed host.
- A public domain name pointing to the managed host's public IP address before enabling `wordpress_https_enabled` to request a Let's Encrypt certificate.
- The `ansible.mysql`, `ansible.windows`, `ansible.netcommon`, and `cisco.ios` Ansible collections, installed from `requirements.yml` on the control node.
- Python package `pywinrm` (required for the Windows group), installed from `requirements.txt` on the control node: `pip install -r requirements.txt`. On distributions with an externally managed Python (PEP 668), use a virtual environment or `sudo apt install python3-winrm` instead of plain `pip`.

## Project layout

```
site.yml                      # entry playbook
router_hostname.yml           # Cisco IOS hostname playbook
router_interfaces.yml         # Cisco IOS interface status report (read-only)
dynamic_inventory.py          # dynamic inventory script (queries the IPAM API)
ansible.cfg                   # Ansible settings (inventory = ./dynamic_inventory.py)
group_vars/webservers.yml     # variables for the webservers group
group_vars/windows.yml        # variables for the windows group (WinRM password env lookup)
group_vars/routers.yml        # Cisco IOS network_cli settings (password env lookup)
roles/packages/tasks/main.yml # installs base packages
roles/router_hostname/        # configures Cisco IOS router hostnames
roles/wordpress/              # Apache, MariaDB, PHP, WordPress and HTTPS deployment
ipam/                         # Django IPAM app (Docker + SQLite + REST API + admin UI)
  Dockerfile                  # image for the API/UI container
  docker-compose.yml          # binds 127.0.0.1:8000 only
  entrypoint.sh               # migrate + gunicorn
  ipam/                       # Django project (settings, urls)
  inventory/                  # models, admin, DRF API, seed command
  data/                       # SQLite volume (gitignored)
scripts/Enable-WinRM.ps1      # enables WinRM on a managed Windows host
requirements.yml              # Ansible collection dependencies (ansible-galaxy)
requirements.txt              # Python dependencies for the control node (pip)
AGENTS.md                     # rules for AI coding agents
.opencode/skills/             # agent skills for this repository
.secret                       # local secrets storage (gitignored, never committed)
.secret.example               # template for .secret with placeholder values
```

## Dynamic inventory and IPAM web UI

Hosts are no longer stored in a static `hosts` file. Inventory data lives in SQLite inside the `ipam` Django application:

- **Web UI (Django Admin):** add, edit, and delete hosts and groups at `http://127.0.0.1:8000/admin/`.
- **REST API:** `GET|POST /api/hosts/`, `GET|POST /api/groups/`, and detail routes `/api/hosts/<id>/`, `/api/groups/<id>/`.
- **Inventory endpoint:** `GET /api/ansible/inventory/` returns the JSON structure Ansible expects.
- **Dynamic inventory script:** `./dynamic_inventory.py` calls that endpoint (Python stdlib only) and is what `ansible.cfg` points at.
- **Group variables** still live in `group_vars/<group>.yml` and are loaded automatically because the inventory script sits in the repository root next to `group_vars/`.

The API/UI container publishes `127.0.0.1:8000` only (not reachable from the LAN). There is no API token; the Django Admin login protects the UI, and the inventory endpoint is open on localhost.

### First-time setup on the Ubuntu control node

Run every command from the repository root.

```bash
# 1) System prerequisites
sudo apt update
sudo apt install -y ansible git python3-winrm python3-paramiko
ansible-galaxy collection install -r requirements.yml

# Docker Engine + Compose plugin: install from the official Docker docs if missing
# https://docs.docker.com/engine/install/ubuntu/
sudo usermod -aG docker "$USER"
newgrp docker

# 2) SSH key used by the webservers (path is stored in the IPAM database)
sudo mkdir -p /etc/ansible/keys
sudo cp /path/to/Stokholm.pem /etc/ansible/keys/Stokholm.pem
sudo chmod 600 /etc/ansible/keys/Stokholm.pem

# 3) Secrets for the Django container
cp ipam/.env.example ipam/.env
# Edit ipam/.env and set DJANGO_SECRET_KEY to a long random string:
#   python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# 4) Build and start the API/UI
cd ipam
docker compose up -d --build
cd ..

# 5) Create the admin user for the web UI (choose username/password when prompted)
docker compose -f ipam/docker-compose.yml exec web python manage.py createsuperuser

# 6) Seed the initial hosts (server1, server2, win1, rtr1.lab, rtr2.lab)
docker compose -f ipam/docker-compose.yml exec web python manage.py seed_inventory

# 7) Make the inventory script executable
chmod +x dynamic_inventory.py
```

### Verify the dynamic inventory (no managed hosts contacted)

```bash
ansible-inventory --graph
ansible-inventory --list
ansible-inventory --host server1
curl -s http://127.0.0.1:8000/api/ansible/inventory/ | python3 -m json.tool
```

### Use the web UI

1. Open `http://127.0.0.1:8000/admin/` and log in with the superuser from step 5.
2. Under **Inventory**, add, edit, or delete hosts and groups.
3. Re-run `ansible-inventory --list` — changes appear immediately (the API is the single source of truth).

Useful API examples:

```bash
curl -s http://127.0.0.1:8000/api/hosts/ | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/api/hosts/ \
  -H 'Content-Type: application/json' \
  -d '{"name":"server3","address":"203.0.113.10","groups":["webservers"],"ansible_user":"ubuntu","ansible_ssh_private_key_file":"/etc/ansible/keys/Stokholm.pem","enabled":true,"variables":{}}'
```

### Day-2 operations

```bash
# Restart or stop the IPAM stack
docker compose -f ipam/docker-compose.yml restart
docker compose -f ipam/docker-compose.yml down        # data stays in ipam/data/

# Logs
docker compose -f ipam/docker-compose.yml logs -f

# Re-seed is safe: existing hosts are skipped
docker compose -f ipam/docker-compose.yml exec web python manage.py seed_inventory
```

If `ansible-inventory --list` fails with a connection error, the container is not running: `docker compose -f ipam/docker-compose.yml ps`.

## WordPress configuration

The `wordpress` role installs or updates Apache, MariaDB, PHP and required PHP extensions from the Ubuntu 24.04 repositories. It deploys WordPress, creates its database and administrator, configures Apache, and requests a Let's Encrypt certificate using Certbot. Certificate renewal is enabled automatically. The role does not install Certbot itself; install it on the target host before switching `wordpress_https_enabled` to `true`.

Set `wordpress_domain`, `wordpress_letsencrypt_email`, and `wordpress_admin_email` in `group_vars/webservers.yml`. Before certificate issuance, the domain must resolve publicly to the server and inbound TCP ports 80 and 443 must be reachable. Other non-secret role settings, such as the database name and site title, are also defined there.

Set `wordpress_https_enabled` to `false` to deploy without HTTPS: no Let's Encrypt certificate is requested, `wordpress_letsencrypt_email` is not required, and the site is served over plain HTTP on port 80. In that mode `wordpress_domain` defaults to each host's inventory IP (`{{ ansible_host }}`), so the playbook can be run against any single host with `--limit`. Set a real domain and switch the flag back to `true` to enable certificate issuance later.

Add `wordpress_db_password` and `wordpress_admin_password` to `group_vars/webservers.yml` as Ansible Vault encrypted variables. Run each command separately, enter the Vault password when prompted, provide the secret on standard input, and press Ctrl-D to finish. Paste each resulting YAML value into that file:

```bash
ansible-vault encrypt_string --ask-vault-pass --stdin-name wordpress_db_password
ansible-vault encrypt_string --ask-vault-pass --stdin-name wordpress_admin_password
```

Never put plaintext passwords or the Vault password in the repository. At playbook runtime, provide the Vault password interactively with `--ask-vault-pass` or use a securely stored Vault password file that is not committed. WP-CLI receives the initial passwords through standard input, and password-bearing Ansible tasks suppress their output. WordPress stores its administrator password as a hash in the database. The database password must also be available to WordPress at runtime, so it is written to `wp-config.php`, owned by `root:www-data` with mode `0640`.

Install the required Ansible collections on the control node:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Run the WordPress deployment

`roles/wordpress/` is an Ansible role, not a standalone playbook. The entry playbook is `site.yml`; it runs the `packages` role first, followed by `wordpress`. Run the following commands from the repository root on the Ubuntu control node, after configuring the variables and installing the collection above.

First, check playbook syntax locally:

```bash
ansible-playbook site.yml --ask-vault-pass --syntax-check
```

Then run a dry run. This contacts the managed hosts and requires approval:

```bash
ansible-playbook site.yml --ask-vault-pass --check --diff
```

After reviewing the dry-run results, obtain explicit approval before applying the deployment:

```bash
ansible-playbook site.yml --ask-vault-pass
```

The deployment command runs both base package setup and WordPress. Check mode does not execute command tasks such as WP-CLI installation or certificate issuance, so it cannot verify those runtime operations.

On the very first deployment the dry run stops at service tasks (for example `Start and enable MariaDB`) with an error such as `Could not find the requested service`, because check mode does not install packages and the service unit does not exist yet. This is expected: review the output up to that point, then run the real deployment. Later dry runs pass completely once the packages are installed.

## Run on one server

`site.yml` normally targets the whole `webservers` group. Pass a host alias with `--limit` to run against one inventory host only:

```bash
# Dry run against server1
ansible-playbook site.yml --ask-vault-pass --check --diff --limit server1

# Apply changes to server1
ansible-playbook site.yml --ask-vault-pass --limit server1

# The same commands work with server2 to target the other host
ansible-playbook site.yml --ask-vault-pass --check --diff --limit server2
```

Both the `packages` and `wordpress` roles run only on the selected host. The alias must exist in the IPAM database (Django Admin) and belong to the `webservers` group. With `wordpress_https_enabled: false` each host serves its own inventory IP, so the same group variables work for either server.

## Verify the Windows host connection

The `[windows]` inventory group contains a Windows host managed over WinRM with the NTLM transport. The connection uses the `winrm` plugin built into ansible-core (`ansible.builtin.winrm`): since ansible-core 2.20 the plugin no longer ships in the `ansible.windows` collection, so `ansible_connection=winrm` is used instead of `ansible.windows.winrm`. The scheme is plain HTTP on port 5985 (`ansible_winrm_scheme=http`, `ansible_winrm_port=5985`), matching the listener created by the setup script. The password is not stored in the repository: it is read from the control node environment variable `windows_pass` by `group_vars/windows.yml`.

First, enable WinRM on the Windows host. Run PowerShell as Administrator on that host and execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\Enable-WinRM.ps1
```

The script enables the WinRM listener, allows Basic authentication, sets the network profile to Private, raises the module memory and timeout limits, and opens the firewall port 5985 for the Private profile. In the AWS Security Group of the Windows host, allow inbound TCP 5985 from the control node IP only.

Then, on the control node, install the extra dependencies:

```bash
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

Set the password for the current shell session:

```bash
export windows_pass='<password>'
```

Verify connectivity to all hosts in the `windows` group:

```bash
ansible windows -m ansible.windows.win_ping
```

A successful connection returns `win1 | SUCCESS => {"changed": false, "ping": "pong"}`. To test a single host, pass the alias: `ansible win1 -m ansible.windows.win_ping`.

The connection uses Basic authentication with unencrypted transport, which is acceptable only inside a private network. Keep port 5985 restricted to the control node IP.

## Manage Cisco IOS routers

The `[routers]` inventory group contains Cisco IOS devices managed over SSH with `ansible.netcommon.network_cli` and the `cisco.ios.ios` network OS plugin. The `site.yml` playbook targets only `webservers`; it does not run the Linux or WordPress roles on routers.

The router password is not stored in the repository. Set `routers_pass` in the control node shell before running Ansible:

```bash
export routers_pass='<password>'
```

On the Ubuntu control node, install Paramiko for Ansible's system Python:

```bash
sudo apt install python3-paramiko
```


Install the collections listed in `requirements.yml` with `ansible-galaxy collection install -r requirements.yml`. To gather IOS facts, run the following read-only query after obtaining approval; it connects to the routers:

```bash
ansible routers -m cisco.ios.ios_facts
```


To send an ICMP ping from each router to a destination, use `cisco.ios.ios_ping` with the destination address. This command also connects to the routers:

```bash
ansible routers -m cisco.ios.ios_ping -a "dest=192.0.2.1"
```


## Show router interface status

The `router_interfaces.yml` playbook is read-only: it gathers interface facts with `cisco.ios.ios_facts` and prints each interface's operational/line protocol status, description, and addresses. It changes no router configuration, so there is no `--check --diff` dry run; the syntax check is local and the run only reads facts.

```bash
export routers_pass='<password>'

ansible-playbook router_interfaces.yml --syntax-check

# All routers
ansible-playbook router_interfaces.yml

# One router
ansible-playbook router_interfaces.yml --limit rtr1.lab
```

Sample output per router:

```
rtr1.lab | ok: [rtr1.lab] => {
    "msg": "\nInterface: GigabitEthernet1\n  Status: up/up\n  Description: \n  Addresses: 10.7.7.1, 10.7.7.10\n..."
}
```


## Configure router hostnames

The `router_hostname.yml` playbook targets only the `[routers]` group. By default, the role derives each IOS hostname from its inventory alias: `rtr1.lab` becomes `rtr1`, and `rtr2.lab` becomes `rtr2`. Changes are saved to startup configuration when a hostname is updated.

Running this playbook changes router configuration. Obtain approval before execution.

Run it against all routers:

```bash
ansible-playbook router_hostname.yml
```

Run it against one router with `--limit`:

```bash
ansible-playbook router_hostname.yml --limit rtr1.lab
```

Override the hostname for one router if needed:

```bash
ansible-playbook router_hostname.yml --limit rtr1.lab -e "router_hostname=edge-rtr1"
```

## Adding packages

Edit `packages_list` in `group_vars/webservers.yml` to change base packages, or `wordpress_packages` to change the WordPress stack packages. Do not duplicate group variables in role defaults.

## Contributing

- Work in a feature branch. Never push to `master`.
- Open a Pull Request against `master`. Pull requests are created through the GitHub MCP server configured in OpenCode; it authenticates with a fine-grained personal access token kept outside the repository (`.secret` is gitignored, and the token reaches OpenCode through the `GITHUB_MCP_PAT` environment variable).
- Commit messages and PR descriptions are written in English.
