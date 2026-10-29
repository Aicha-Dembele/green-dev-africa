from django.urls import path

from . import views

urlpatterns = [
    path("mes-credits/", views.mes_credits, name="mes_credits"),
]
