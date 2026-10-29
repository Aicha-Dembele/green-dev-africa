from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from .models import JournalCredits, SoldeCredits
from .services import ajouter_credits


class AjouterCreditsForm(forms.Form):
    montant = forms.IntegerField(label="Montant", min_value=1)
    note = forms.CharField(label="Note", max_length=255, required=False)


@admin.register(SoldeCredits)
class SoldeCreditsAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "solde")
    search_fields = ("utilisateur__username", "utilisateur__nom")
    readonly_fields = ("utilisateur", "solde")
    change_form_template = "admin/credits/soldecredits/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:pk>/ajouter-credits/",
                self.admin_site.admin_view(self.ajouter_credits_view),
                name="credits_soldecredits_ajouter_credits",
            )
        ]
        return custom_urls + urls

    def ajouter_credits_view(self, request, pk):
        solde = self.get_object(request, pk)
        if solde is None:
            return redirect("admin:credits_soldecredits_changelist")

        form = AjouterCreditsForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            ajouter_credits(
                solde.utilisateur,
                form.cleaned_data["montant"],
                JournalCredits.Type.AJUSTEMENT_ADMIN,
                form.cleaned_data["note"] or "Ajustement manuel",
            )
            self.message_user(
                request,
                f"{solde.utilisateur} a reçu {form.cleaned_data['montant']} crédits.",
            )
            return redirect("admin:credits_soldecredits_change", solde.pk)

        context = {
            **self.admin_site.each_context(request),
            "title": "Ajouter des crédits",
            "opts": self.model._meta,
            "solde": solde,
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/credits/soldecredits/ajouter_credits.html",
            context,
        )


@admin.register(JournalCredits)
class JournalCreditsAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "date", "montant", "type", "note", "analyse")
    list_filter = ("type", "utilisateur")
    search_fields = ("utilisateur__username", "utilisateur__nom", "note")
    readonly_fields = ("utilisateur", "date", "montant", "type", "note", "analyse")
    ordering = ("-date", "-pk")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
