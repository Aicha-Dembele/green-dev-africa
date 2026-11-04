from django.urls import path

from . import views

urlpatterns = [
    path("mes-credits/", views.mes_credits, name="mes_credits"),
    path("acheter/", views.acheter_credits, name="acheter_credits"),
]
