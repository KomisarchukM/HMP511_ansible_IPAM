from rest_framework import serializers

from ..models import Group, Host


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "description"]


class HostSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Group.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Host
        fields = [
            "id",
            "name",
            "address",
            "groups",
            "enabled",
            "ansible_user",
            "ansible_port",
            "ansible_connection",
            "ansible_network_os",
            "ansible_ssh_private_key_file",
            "variables",
        ]
