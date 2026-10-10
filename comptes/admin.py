"""Administration des comptes et des notifications."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Notification, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """On reprend l'admin de Django et on y ajoute nos deux champs."""

    list_display = ("username", "nom", "email", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "nom", "email")

    # Les blocs du formulaire : on insère « nom » et « rôle » dans l'identité.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Identité", {"fields": ("nom", "email", "first_name", "last_name")}),
        ("Rôle dans Green Dev", {"fields": ("role",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "nom", "email", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type", "message", "date_envoi", "lu")
    list_filter = ("type", "lu")
    search_fields = ("message", "utilisateur__nom")
    date_hierarchy = "date_envoi"
