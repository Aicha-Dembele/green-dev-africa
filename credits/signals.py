from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from credits.services import attribuer_credits_bienvenue


@receiver(post_save, sender=get_user_model())
def attribuer_bienvenue(sender, instance, created, **kwargs):
    if created:
        attribuer_credits_bienvenue(instance)
