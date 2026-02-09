from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_profile_for_superuser(sender, instance, created, **kwargs):
    """Auto-create a UserProfile with SUPER_ADMIN role when a superuser is saved."""
    if not instance.is_superuser:
        return
    from .models import UserProfile
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={'role': 'SUPER_ADMIN'},
    )
