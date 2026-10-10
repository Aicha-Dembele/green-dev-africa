"""Adresses du site Green Dev Africa.

Ce fichier ne fait que distribuer : chaque application tient la liste de ses
propres adresses dans son fichier `urls.py`.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comptes/", include("comptes.urls")),
    path("", include("analyses.urls")),
    # Les projets en dernier : leur adresse "" est le tableau de bord.
    path("", include("projets.urls")),
]
