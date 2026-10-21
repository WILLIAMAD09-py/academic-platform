# Migraciones Alembic

Las migraciones se generan en el paso 4 ("Persistencia: ORM, repositorios, primera migración
Alembic") con:

```bash
alembic revision --autogenerate -m "initial schema"
```

Este archivo mantiene el directorio en el repositorio mientras no exista la primera revisión.
