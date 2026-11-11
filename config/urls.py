"""Adresses du site Green Dev Africa.

Ce fichier ne fait que distribuer : chaque application tient la liste de ses
propres adresses dans son fichier `urls.py`.
"""

from django.contrib import admin
from django.urls import include, path

from credits.views import tarifs

urlpatterns = [
    path("admin/", admin.site.urls),
    path("tarifs/", tarifs, name="tarifs"),
    path("comptes/", include("comptes.urls")),
    path("credits/", include("credits.urls")),
    path("", include("analyses.urls")),
    # Les projets en dernier : leur adresse "" est le tableau de bord.
    path("", include("projets.urls")),
]
