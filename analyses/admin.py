"""Administration des analyses : le poste de pilotage du back-end.

Les pièces d'une analyse (configuration, contexte, indicateurs, ressources,
problèmes) s'affichent dans la fiche de l'analyse : c'est la traduction
visuelle des compositions du diagramme.
"""

from django.contrib import admin

from .models import (
    Analyse,
    ComparaisonAnalyse,
    ConfigurationAnalyse,
    ConseilOptimisation,
    Indicateur,
    PartageRapport,
    ProblemeDetecte,
    Rapport,
    Recommandation,
    RegleAnalyse,
    RessourceWeb,
    UtilisateurContexte,
)


# --- référentiels ---


@admin.register(RegleAnalyse)
class RegleAnalyseAdmin(admin.ModelAdmin):
    list_display = ("code", "categorie", "seuil", "active")
    list_filter = ("categorie", "active")
    list_editable = ("seuil", "active")  # l'administrateur règle les seuils d'un coup
    search_fields = ("code", "description")


@admin.register(ConseilOptimisation)
class ConseilOptimisationAdmin(admin.ModelAdmin):
    list_display = ("titre", "categorie", "gain_attendu")
    list_filter = ("categorie",)
    search_fields = ("titre", "explication", "solution_technique")


# --- les pièces d'une analyse, affichées dans sa fiche ---


class ConfigurationInline(admin.StackedInline):
    model = ConfigurationAnalyse
    extra = 0


class ContexteInline(admin.StackedInline):
    model = UtilisateurContexte
    extra = 0
    max_num = 1  # relation 1 -- 1 du diagramme


class IndicateurInline(admin.TabularInline):
    model = Indicateur
    extra = 0


class RessourceInline(admin.TabularInline):
    model = RessourceWeb
    extra = 0


class ProblemeInline(admin.TabularInline):
    model = ProblemeDetecte
    extra = 0
    fields = ("titre", "regle", "gravite", "statut")
    show_change_link = True


@admin.register(Analyse)
class AnalyseAdmin(admin.ModelAdmin):
    list_display = ("projet", "date_analyse", "statut", "score_global")
    list_filter = ("statut", "date_analyse")
    search_fields = ("projet__nom", "projet__url")
    date_hierarchy = "date_analyse"
    inlines = [
        ConfigurationInline,
        ContexteInline,
        IndicateurInline,
        RessourceInline,
        ProblemeInline,
    ]
    actions = ["action_executer_analyse"]

    @admin.action(description="Exécuter l'analyse (détection + score + rapport)")
    def action_executer_analyse(self, request, queryset):
        """Permet de tester toute la chaîne depuis l'admin, sans écrire de vue."""
        for analyse in queryset:
            analyse.executer_analyse()
        self.message_user(request, f"{queryset.count()} analyse(s) exécutée(s).")


# --- problèmes et recommandations ---


class RecommandationInline(admin.StackedInline):
    model = Recommandation
    extra = 0


@admin.register(ProblemeDetecte)
class ProblemeDetecteAdmin(admin.ModelAdmin):
    list_display = ("titre", "analyse", "regle", "gravite", "statut")
    list_filter = ("gravite", "statut", "regle__categorie")
    search_fields = ("titre", "description", "localisation")
    inlines = [RecommandationInline]


@admin.register(Recommandation)
class RecommandationAdmin(admin.ModelAdmin):
    list_display = ("titre", "probleme", "priorite", "categorie", "statut")
    list_filter = ("priorite", "statut", "categorie")
    search_fields = ("titre", "description")


@admin.register(RessourceWeb)
class RessourceWebAdmin(admin.ModelAdmin):
    list_display = ("url", "type", "taille", "optimisable", "analyse")
    list_filter = ("type", "optimisable")
    search_fields = ("url",)


@admin.register(Indicateur)
class IndicateurAdmin(admin.ModelAdmin):
    list_display = ("nom", "valeur", "unite", "categorie", "analyse")
    list_filter = ("categorie", "nom")
    search_fields = ("nom",)


# --- sorties : rapport, partage, comparaison ---


class PartageInline(admin.TabularInline):
    model = PartageRapport
    extra = 0
    readonly_fields = ("jeton", "date_creation")


@admin.register(Rapport)
class RapportAdmin(admin.ModelAdmin):
    list_display = (
        "analyse",
        "date_generation",
        "green_score",
        "poids_total",
        "nombre_requetes",
        "temps_chargement",
    )
    list_filter = ("date_generation",)
    search_fields = ("analyse__projet__nom",)
    inlines = [PartageInline]


@admin.register(PartageRapport)
class PartageRapportAdmin(admin.ModelAdmin):
    list_display = ("rapport", "jeton", "date_creation", "date_expiration", "actif")
    list_filter = ("actif",)
    readonly_fields = ("jeton",)


@admin.register(ComparaisonAnalyse)
class ComparaisonAnalyseAdmin(admin.ModelAdmin):
    list_display = (
        "date_comparaison",
        "analyse_avant",
        "analyse_apres",
        "score_avant",
        "score_apres",
        "evolution",
        "taux_amelioration",
    )
    readonly_fields = (
        "score_avant",
        "score_apres",
        "ecart_poids",
        "evolution",
        "taux_amelioration",
    )
    actions = ["action_comparer"]

    @admin.action(description="Comparer les résultats (recalcule l'évolution)")
    def action_comparer(self, request, queryset):
        for comparaison in queryset:
            comparaison.comparer_resultats()
        self.message_user(request, f"{queryset.count()} comparaison(s) recalculée(s).")
