from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = "Create or update the default superuser"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        username = settings.ADMIN_USERNAME
        email = settings.ADMIN_EMAIL
        password = settings.ADMIN_PASSWORD

        if not username or not password:
            self.stdout.write(
                self.style.WARNING("Admin credentials not configured.")
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' updated.")
            )