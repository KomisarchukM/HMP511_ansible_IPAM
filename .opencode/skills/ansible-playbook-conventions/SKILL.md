---
name: ansible-playbook-conventions
description: Conventions for writing Ansible playbooks and roles in this repository. Use when creating or editing site.yml, roles, tasks, handlers, group_vars, or when the user asks to write or review an Ansible playbook.
---

# Ansible Playbook Conventions

## Module names

- Always use fully qualified collection names (FQCN): `ansible.builtin.apt`, `ansible.builtin.service`, `ansible.builtin.copy`.
- Never use short module names like `apt` or `copy`.

## Structure

```
site.yml                      # entry playbook
group_vars/<group>.yml        # variables shared by a group
roles/<role>/tasks/main.yml   # role tasks
roles/<role>/handlers/main.yml
roles/<role>/defaults/main.yml  # only if needed; prefer group_vars
```

- Put variables in `group_vars/`, not duplicated in role `defaults/`.
- Keep one source of truth for each variable.
- Declare external collections in the repository `requirements.yml` and document how to install them on the control node.

## WordPress role

- Target Ubuntu Server 24.04. Install the current supported PHP version and extensions from the Ubuntu APT repositories; do not add an unrequested third-party PHP repository.
- Keep WordPress, Apache, MariaDB, and PHP settings in `group_vars/webservers.yml`.
- Manage MariaDB databases and users with `ansible.mysql`; install the target-side Python MySQL driver and use the local Unix socket for root administration where supported.
- Keep `wordpress_db_password` and `wordpress_admin_password` encrypted with Ansible Vault. Never commit plaintext secrets or pass passwords as command-line arguments.
- Keep `acl` in `packages_list`: Ansible needs `setfacl` on the target host to grant its temporary files to an unprivileged `become_user` such as `www-data`.
- When using WP-CLI with a secret, read it through `--prompt=<argument>` and the command module's `stdin`; mark the task `no_log: true`.
- Make WordPress configuration and Apache virtual hosts repeatable. When `wordpress_https_enabled` is `true`, also keep Certbot issuance and certificate renewal repeatable, and preserve the HTTP ACME challenge path when redirecting other HTTP traffic to HTTPS.
- When `wordpress_https_enabled` is `true`, require a configured public domain and contact email before certificate issuance. Do not run deployment tasks against hosts without explicit approval.

## Windows hosts

- Windows hosts live in the `windows` inventory group only. Never add them to `webservers`: `site.yml` and its roles target Ubuntu (apt, Apache, MariaDB).
- Connection settings in `hosts`:
  - `ansible_connection=winrm` — the plugin built into ansible-core (since 2.20 the `ansible.windows.winrm` FQCN no longer exists).
  - `ansible_winrm_scheme=http` and `ansible_winrm_port=5985` — the listener created by `scripts/Enable-WinRM.ps1` is plain HTTP; the default scheme is HTTPS on 5986 and will time out.
  - `ansible_winrm_transport=ntlm` and `ansible_winrm_server_cert_validation=ignore`.
- The password must never appear in `hosts` or role files. It is read in `group_vars/windows.yml` through `lookup('env', 'windows_pass')` and set on the control node with `export windows_pass='<password>'`. Mark tasks that handle Windows credentials `no_log: true`.
- WinRM prerequisites on the Windows host: run `scripts/Enable-WinRM.ps1` as Administrator, open inbound TCP 5985 in the AWS Security Group for the control node IP only, and install `python3-winrm` on the control node.
- Test connectivity with `ansible windows -m ansible.windows.win_ping`; expected success output is `{"ping": "pong"}`.

## Cisco IOS routers

- Cisco IOS devices belong in the `routers` inventory group only. Do not add them to `webservers`; the site playbook and its Linux roles target Ubuntu hosts.
- Configure the group in `group_vars/routers.yml` with `ansible.netcommon.network_cli` and `cisco.ios.ios`. Declare both collections in `requirements.yml`.
- Never store the router password in `hosts` or group variables. Read it from the control node environment variable `routers_pass` with `lookup('env', 'routers_pass')`.
- Router connectivity and facts checks contact managed devices and require explicit user approval before running.

## Idempotency

- Every task must be safe to run repeatedly.
- Use the module's `state` parameter (`present`, `absent`, `started`, `restarted`) instead of `command` or `shell` when a module exists.
- If `command` or `shell` is unavoidable, add `creates:`, `removes:`, or `changed_when:`.

## Privilege escalation

- Set `become: true` only where root is required (at play or task level).
- Do not set `become` for tasks that do not need it.

## Naming

- Task names, handler names, and comments are in English.
- Start each task name with a verb: `Install base packages`, `Restart nginx`.

## Verification before running

Run these in order and fix any failure before proceeding:

```bash
ansible-playbook site.yml --syntax-check
ansible-playbook site.yml --check --diff
```

Note: `--check` does not execute `command` or `shell` tasks, and does not catch errors that appear only at runtime (for example, a non-existent package name).

## Rules

- Do not run the playbook against hosts without explicit user approval.
- Do not modify `hosts` without explicit user approval.
