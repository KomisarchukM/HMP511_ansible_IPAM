# HMP511 Ansible

Ansible playbooks for configuring Linux hosts on AWS and Cisco IOS routers.

## Requirements

- Control node: Ubuntu Linux with `ansible-core` installed system-wide (tested with 2.21.x). The control node is reachable for maintenance as `master@192.168.1.151`; its SSH password is stored locally in `.secret` under `host_pass` and is never committed.
- Managed WordPress host: Ubuntu Server 24.04. Inbound TCP port 80 must be reachable from the internet; port 443 is additionally required when `wordpress_https_enabled` is `true`.
- Managed Windows host (optional, `windows` group): WinRM enabled on TCP port 5985, reachable from the control node, with the `pywinrm` package and the `ansible.windows` collection installed.
- Cisco IOS routers (optional, `routers` group): reachable from the control node over SSH on TCP port 22; keep the login password in the control node environment variable `routers_pass`.
- SSH private key `Stockholm_3.pem` at `/etc/ansible/keys/` on the control node. The key is never committed.
- Passwordless `sudo` for the `ubuntu` user on each managed host.
- A public domain name pointing to the managed host's public IP address before enabling `wordpress_https_enabled` to request a Let's Encrypt certificate.
- The `ansible.mysql`, `ansible.windows`, `ansible.netcommon`, and `cisco.ios` Ansible collections, installed from `requirements.yml` on the control node.
- Python package `pywinrm` (required for the Windows group), installed from `requirements.txt` on the control node: `pip install -r requirements.txt`. On distributions with an externally managed Python (PEP 668), use a virtual environment or `sudo apt install python3-winrm` instead of plain `pip`.

## Project layout

```
site.yml                      # entry playbook
hosts                         # inventory (groups: webservers, windows, routers)
ansible.cfg                   # Ansible settings (inventory = ./hosts)
group_vars/webservers.yml     # variables for the webservers group
group_vars/windows.yml        # variables for the windows group (WinRM password env lookup)
group_vars/routers.yml        # Cisco IOS network_cli settings (password env lookup)
roles/packages/tasks/main.yml # installs base packages
roles/wordpress/              # Apache, MariaDB, PHP, WordPress and HTTPS deployment
scripts/Enable-WinRM.ps1      # enables WinRM on a managed Windows host
requirements.yml              # Ansible collection dependencies (ansible-galaxy)
requirements.txt              # Python dependencies for the control node (pip)
AGENTS.md                     # rules for AI coding agents
.opencode/skills/             # agent skills for this repository
.secret                       # local secrets storage (gitignored, never committed)
.secret.example               # template for .secret with placeholder values
```

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

Both the `packages` and `wordpress` roles run only on the selected host. The alias must exist in `hosts` and belong to the `webservers` group. With `wordpress_https_enabled: false` each host serves its own inventory IP, so the same group variables work for either server.

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

Install the collections listed in `requirements.yml` with `ansible-galaxy collection install -r requirements.yml`. To gather IOS facts, run the following read-only query after obtaining approval; it connects to the routers:

```bash
ansible routers -m cisco.ios.ios_facts
```


To send an ICMP ping from each router to a destination, use `cisco.ios.ios_ping` with the destination address. This command also connects to the routers:

```bash
ansible routers -m cisco.ios.ios_ping -a "dest=192.0.2.1"
```

## Adding packages

Edit `packages_list` in `group_vars/webservers.yml` to change base packages, or `wordpress_packages` to change the WordPress stack packages. Do not duplicate group variables in role defaults.

## Contributing

- Work in a feature branch. Never push to `master`.
- Open a Pull Request against `master`. Pull requests are created through the GitHub MCP server configured in OpenCode; it authenticates with a fine-grained personal access token kept outside the repository (`.secret` is gitignored, and the token reaches OpenCode through the `GITHUB_MCP_PAT` environment variable).
- Commit messages and PR descriptions are written in English.
