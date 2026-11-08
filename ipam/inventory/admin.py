from django.contrib import admin

from .models import Group, Host


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "host_count")
    search_fields = ("name", "description")
    ordering = ("name",)

    @admin.display(description="Hosts")
    def host_count(self, obj):
        return obj.hosts.count()


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "address",
        "group_list",
        "enabled",
        "ansible_user",
        "ansible_connection",
    )
    list_filter = ("enabled", "groups", "ansible_connection")
    search_fields = ("name", "address", "ansible_user")
    filter_horizontal = ("groups",)
    fieldsets = (
        (
            "Identity",
            {
                "fields": ("name", "address", "groups", "enabled"),
            },
        ),
        (
            "Connection",
            {
                "fields": (
                    "ansible_user",
                    "ansible_port",
                    "ansible_connection",
                    "ansible_network_os",
                    "ansible_ssh_private_key_file",
                ),
            },
        ),
        (
            "Extra variables",
            {
                "fields": ("variables",),
                "description": (
                    "JSON object merged into the hostvars, "
                    "for example ansible_winrm_scheme"
                ),
            },
        ),
    )

    @admin.display(description="Groups")
    def group_list(self, obj):
        return ", ".join(g.name for g in obj.groups.all())
