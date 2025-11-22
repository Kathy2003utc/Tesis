from django.db import migrations
from django.contrib.auth.hashers import make_password

def crear_admin(apps, schema_editor):
    Usuario = apps.get_model('gestionPedidos', 'Usuario')  # tu app y modelo exactos
    if not Usuario.objects.filter(correo="admin@restaurante.com").exists():
        Usuario.objects.create(
            nombre="Dueño",
            apellido="Restaurante",
            correo="admin@restaurante.com",
            username="admin@restaurante.com",
            password=make_password("AdminSeguro123"),  # contraseña segura cifrada
            rol="admin",
            is_staff=True,
            is_superuser=True
        )

class Migration(migrations.Migration):

    dependencies = [
        ('gestionPedidos', '0008_alter_pedido_estado'),  # la migración anterior
    ]

    operations = [
        migrations.RunPython(crear_admin),
    ]
