from core.models import Perfil

from django.contrib.auth import get_user_model
from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand
from django.core.management.base import CommandError

class Command(BaseCommand):
    def handle(self, *args, **options):
        first_name = options.pop("first_name", None)
        if not first_name:
            first_name = input("Apelido: ").strip()
        if not first_name:
            raise CommandError("Apelido obrigatório.")
        database = options.get("database")
        User = get_user_model()
        manager = User._default_manager.db_manager(database)
        before = set(manager.values_list("pk", flat=True))
        result = super().handle(*args, **options)
        user = manager.exclude(pk__in=before).order_by("-pk").first()
        if user is None:
            raise CommandError("Administrador não foi criado.")
        user.first_name = first_name
        user.save(update_fields=["first_name"])
        Perfil.objects.create(usuario=user, departamento='ti')
        return result
