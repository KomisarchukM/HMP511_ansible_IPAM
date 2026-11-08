from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"groups", views.GroupViewSet)
router.register(r"hosts", views.HostViewSet)

urlpatterns = [
    path("ansible/inventory/", views.ansible_inventory, name="ansible-inventory"),
    path("", include(router.urls)),
]
