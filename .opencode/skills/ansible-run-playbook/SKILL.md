---
name: ansible-run-playbook
description: Procedure for checking inventory connectivity and running Ansible playbooks against webservers, Windows hosts, and Cisco IOS routers from the Ubuntu control node. Use when the user asks to run, test, verify, or deploy a playbook, check host connectivity, or diagnose the control node over SSH.
---

# Run Ansible Playbook

Runs on the Linux control node from the repository root.

## Prerequisites

Check before running. Stop and report if any check fails.

```bash
ansible --version                       # ansible-core must be installed
test -f /etc/ansible/keys/Stockholm_3.pem && echo "key OK"
ansible-galaxy collection install -r requirements.yml
```

Control node environment notes:

- `ansible` is installed system-wide via `apt` and runs under `/usr/bin/python3`. A virtualenv does NOT contain ansible: even with `(env)` active, `which ansible` falls through to `/usr/bin/ansible`, and pip packages installed in the venv are invisible to it. Do not rely on a venv.
- Python dependencies must be installed system-wide. Plain `pip3 install` fails with `externally-managed-environment` (PEP 668). Use the distro package instead: `sudo apt install python3-winrm`.

For WordPress, confirm that both passwords are encrypted with Ansible Vault and do not print or expose Vault values while checking configuration. Additionally, when `wordpress_https_enabled` is `true`, confirm that the required domain and email variables are set in `group_vars/webservers.yml`, the public DNS record points to the target host, and ports 80 and 443 are reachable for Let's Encrypt. Plain HTTP mode needs only inbound port 80 and a reachable inventory IP.

For Windows hosts, additionally check `python3-winrm` and export the password before any WinRM command:

```bash
python3 -c "import winrm; print('pywinrm OK')"
export windows_pass='<password>'
```

For Cisco IOS routers, install the `ansible.netcommon` and `cisco.ios` collections from `requirements.yml` and export the password before connecting:

```bash
export routers_pass='<password>'
```

## Steps

Ask for explicit approval before each step that contacts managed hosts. A syntax check is local and does not need host approval. Review the dry-run output and obtain a separate explicit approval before applying changes.

1. Verify inventory (read-only):
   ```bash
   ansible-inventory --list
   ```
2. Check playbook syntax (local only):
   ```bash
   ansible-playbook site.yml --ask-vault-pass --syntax-check
   ```
3. Check connectivity (contacts hosts; ask for approval first):
   ```bash
   ansible webservers -m ansible.builtin.ping
   ansible windows -m ansible.windows.win_ping   # requires export windows_pass=...
   ansible routers -m cisco.ios.ios_facts       # requires export routers_pass=...
   ```
4. Dry run (contacts hosts, changes nothing; ask for approval first):
   ```bash
   ansible-playbook site.yml --ask-vault-pass --check --diff
   ```
5. Real run (changes hosts; requires separate explicit approval after the dry run is reviewed):
   ```bash
   ansible-playbook site.yml --ask-vault-pass
   ```

The `site.yml` commands target only `webservers`. Append `--limit <host>` (for example `--limit server1`) to a `site.yml` command to run against one webserver. The Cisco IOS facts command targets the `routers` group and contacts those devices.

## Verification after a real run

Verify WordPress deployment without displaying credentials:

```bash
ansible webservers -m ansible.builtin.command -a "systemctl is-active apache2 mariadb" --limit <host>
curl --fail --silent --show-error --head http://<inventory-ip>/
```

When `wordpress_https_enabled` is `true`, also verify the certificate side (Certbot is not installed by the role; it must already be present on the host):

```bash
ansible webservers -m ansible.builtin.command -a "systemctl is-active certbot.timer"
ansible webservers -m ansible.builtin.command -a "certbot certificates"
curl --fail --silent --show-error --head https://<domain>/
```

The database password is necessarily stored in the target `wp-config.php` for WordPress to connect to MariaDB; the role restricts that file to `root:www-data` with mode `0640`. WordPress stores the administrator password as a hash in the database. Never include either password in verification commands or logs.

## Diagnostics on the control node over SSH

The control node is reachable from the dev machine as `master@192.168.1.151`. The SSH password is stored in the local `.secret` file under the `host_pass` key; never print it or put it literally in a command string. On Windows use `plink` (PuTTY):

```powershell
$pass = ((Get-Content .secret | Where-Object { $_ -like 'host_pass=*' }) -replace '^host_pass=','').Trim()
echo y | & "C:\Program Files\PuTTY\plink.exe" -ssh -pw $pass master@192.168.1.151 "cd /home/master/HMP511_ansible && <read-only command>"
```

`echo y |` accepts the host key on the first connection. Ask for explicit user approval before connecting. Only read-only diagnostics are allowed over SSH (no file edits, no installs, no playbook runs); anything that changes state needs separate approval and should be done by the user or through an approved playbook run.

Useful read-only diagnostic commands:

```bash
ansible --version                                  # which ansible, which python, collection paths
ansible-doc -t connection -l                       # available connection plugins
ansible-galaxy collection list                     # installed collections and their paths
ansible-config dump | grep -i COLLECTIONS          # effective collection paths
ansible-inventory --host win1                      # effective host variables
cat hosts                                          # inventory state
```

## Failure handling

- If `ping` fails with a permission error, check the key path and `ansible_user` in `hosts`.
- Windows/WinRM errors:
  - `the connection plugin 'ansible.windows.winrm' was not found`: since ansible-core 2.20 the WinRM connection plugin is built into ansible-core. Use `ansible_connection=winrm` (short name of `ansible.builtin.winrm`) in the inventory; do not use the `ansible.windows.winrm` FQCN.
  - Connection timeout to port **5986**: the default WinRM scheme is HTTPS. This setup uses plain HTTP on 5985, so the host needs `ansible_winrm_scheme=http` and `ansible_winrm_port=5985`.
  - `error: externally-managed-environment` from pip: install the distro package instead (`sudo apt install python3-winrm`); do not use a venv for the system ansible.
  - If `ansible-galaxy collection list` shows a collection but ansible cannot find its plugin, compare the collection path with `ansible-config dump | grep -i COLLECTIONS`: the repo-level `ansible.cfg` overrides the system one and may exclude the path where the collection is installed.
- If a task fails, stop and report the task name and error. Do not retry with different options without approval.
- Do not run with `--force-handlers` or `--skip-tags` unless the user asks.
- If `wordpress_https_enabled` is `true` and Certbot cannot issue a certificate, stop and verify domain DNS and inbound port 80 before proposing a retry; do not bypass certificate checks.
- On the very first deployment, check mode stops at service tasks (for example `Start and enable MariaDB`) with `Could not find the requested service`, because check mode does not install packages. This is expected; review the output up to that point and proceed to the real run after approval. Do not treat it as a role failure.
- Check mode does not execute WP-CLI or Certbot command tasks, so successful dry-run output does not prove site installation or certificate issuance.
