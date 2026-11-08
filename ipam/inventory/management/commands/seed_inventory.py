from django.core.management.base import BaseCommand

from inventory.models import Group, Host

GROUPS = {
    "webservers": "Linux web servers on AWS",
    "windows": "Windows host managed over WinRM",
    "routers": "Cisco IOS routers",
}

HOSTS = [
    {
        "name": "server1",
        "address": "16.16.218.174",
        "groups": ["webservers"],
        "ansible_user": "ubuntu",
        "ansible_ssh_private_key_file": "/etc/ansible/keys/Stokholm.pem",
    },
    {
        "name": "server2",
        "address": "13.63.175.210",
        "groups": ["webservers"],
        "ansible_user": "ubuntu",
        "ansible_ssh_private_key_file": "/etc/ansible/keys/Stokholm.pem",
    },
    {
        "name": "win1",
        "address": "13.61.188.65",
        "groups": ["windows"],
        "ansible_user": "Administrator",
        "ansible_connection": "winrm",
        "variables": {
            "ansible_winrm_scheme": "http",
            "ansible_winrm_port": 5985,
            "ansible_winrm_transport": "ntlm",
            "ansible_winrm_server_cert_validation": "ignore",
        },
    },
    {
        "name": "rtr1.lab",
        "address": "10.7.7.10",
        "groups": ["routers"],
        "ansible_user": "master",
        "ansible_port": 22,
    },
    {
        "name": "rtr2.lab",
        "address": "10.7.7.20",
        "groups": ["routers"],
        "ansible_user": "master",
        "ansible_port": 22,
    },
]


class Command(BaseCommand):
    help = "Seed inventory groups and hosts from the original static hosts file"

    def handle(self, *args, **options):
        for name, description in GROUPS.items():
            _, created = Group.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"created group {name}"))
            else:
                self.stdout.write(f"group {name} already exists")

        for data in HOSTS:
            name = data["name"]
            if Host.objects.filter(name=name).exists():
                self.stdout.write(f"host {name} already exists, skipping")
                continue
            group_names = data.pop("groups")
            host = Host.objects.create(**data)
            host.groups.set(Group.objects.filter(name__in=group_names))
            self.stdout.write(self.style.SUCCESS(f"created host {name}"))

        self.stdout.write(self.style.SUCCESS("seed complete"))
