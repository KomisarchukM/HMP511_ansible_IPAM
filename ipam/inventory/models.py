from django.db import models


class Group(models.Model):
    """Inventory group (webservers, windows, routers, ...)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Host(models.Model):
    """Inventory host with Ansible connection variables."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Inventory alias, for example server1 or rtr1.lab",
    )
    address = models.GenericIPAddressField(help_text="ansible_host IP address")
    groups = models.ManyToManyField(
        Group,
        related_name="hosts",
        blank=True,
        help_text="Inventory groups this host belongs to",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Disabled hosts are omitted from the dynamic inventory",
    )
    ansible_user = models.CharField(max_length=100, blank=True)
    ansible_port = models.PositiveIntegerField(null=True, blank=True)
    ansible_connection = models.CharField(
        max_length=100,
        blank=True,
        help_text="ssh, winrm, network_cli; empty means Ansible default",
    )
    ansible_network_os = models.CharField(
        max_length=100,
        blank=True,
        help_text="For example cisco.ios.ios",
    )
    ansible_ssh_private_key_file = models.CharField(max_length=500, blank=True)
    variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra host vars merged into the inventory, e.g. ansible_winrm_*",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def to_hostvars(self):
        """Build the Ansible hostvars mapping for this host."""
        hostvars = {"ansible_host": self.address}
        if self.ansible_user:
            hostvars["ansible_user"] = self.ansible_user
        if self.ansible_port:
            hostvars["ansible_port"] = self.ansible_port
        if self.ansible_connection:
            hostvars["ansible_connection"] = self.ansible_connection
        if self.ansible_network_os:
            hostvars["ansible_network_os"] = self.ansible_network_os
        if self.ansible_ssh_private_key_file:
            hostvars["ansible_ssh_private_key_file"] = self.ansible_ssh_private_key_file
        if isinstance(self.variables, dict):
            hostvars.update(self.variables)
        return hostvars
