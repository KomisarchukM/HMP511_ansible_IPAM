from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Group, Host
from .serializers import GroupSerializer, HostSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class HostViewSet(viewsets.ModelViewSet):
    queryset = Host.objects.prefetch_related("groups")
    serializer_class = HostSerializer


def build_inventory():
    """Return the Ansible dynamic inventory structure."""
    inventory = {"_meta": {"hostvars": {}}}
    hostvars = inventory["_meta"]["hostvars"]

    enabled_hosts = Host.objects.filter(enabled=True).prefetch_related("groups")
    for host in enabled_hosts:
        hostvars[host.name] = host.to_hostvars()

    for group in Group.objects.all().prefetch_related("hosts"):
        names = sorted(
            host.name
            for host in group.hosts.all()
            if host.enabled
        )
        if names:
            inventory[group.name] = {"hosts": names}

    return inventory


@api_view(["GET"])
def ansible_inventory(request):
    return Response(build_inventory())
