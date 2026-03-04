from django.db import migrations
from django.contrib.auth.hashers import make_password
import os

def crear_admin(apps, schema_editor):
    Usuario = apps.get_model('gestionPedidos', 'Usuario')

    admin_email = os.getenv("ADMIN_EMAIL", "morales.carlosgerardo80@gmail.com")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        return  # Si no hay contraseña definida, no crea nada

    if not Usuario.objects.filter(correo=admin_email).exists():
        Usuario.objects.create(
            nombre="Dueño",
            apellido="Restaurante",
            correo=admin_email,
            username=admin_email,
            password=make_password(admin_password),
            rol="admin",
            is_staff=True,
            is_superuser=True
        )

class Migration(migrations.Migration):

    dependencies = [
        ('gestionPedidos', '0008_alter_pedido_estado'),
    ]

    operations = [
        migrations.RunPython(crear_admin),
    ]