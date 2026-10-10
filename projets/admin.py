"""Administration des projets et de leurs objectifs."""

from django.contrib import admin

from .models import ObjectifOptimisation, Projet


class ObjectifInline(admin.TabularInline):
    """Les objectifs se saisissent directement dans la fiche du projet."""

    model = ObjectifOptimisation
    extra = 1


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ("nom", "url", "utilisateur", "statut", "date_creation")
    list_filter = ("statut", "date_creation")
    search_fields = ("nom", "url", "utilisateur__nom")
    inlines = [ObjectifInline]


@admin.register(ObjectifOptimisation)
class ObjectifOptimisationAdmin(admin.ModelAdmin):
    list_display = ("nom", "projet", "valeur_cible", "unite", "date_limite", "statut")
    list_filter = ("statut", "unite")
    search_fields = ("nom", "projet__nom")
