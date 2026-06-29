from logging.config import fileConfig
from pathlib import Path
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool


from alembic import context

SRC_ROOT = Path(__file__).resolve().parents[4]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scheme.minirag_base import SQLAlchemyBase
from models import token_model, user_model  # noqa: F401


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def _resolve_db_url() -> str | None:
    """Prefer an explicit DATABASE_URL, else build one from POSTGRES_* env vars.

    Lets migrations run inside Docker (where the URL comes from the environment)
    without hardcoding credentials in alembic.ini. Alembic runs synchronously, so
    we use the psycopg2 driver here even though the app itself uses asyncpg.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url.replace("postgres://", "postgresql+psycopg2://").replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

    user = os.getenv("POSTGRES_USERNAME") or os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")
    if all([user, password, host, db]):
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return None


# Prefer an env-derived URL whenever POSTGRES_*/DATABASE_URL are present (the Docker
# case): the image may bake an alembic.ini pointing at localhost, which is wrong inside
# a container. With no such env vars (local runs), fall back to whatever alembic.ini holds.
_env_url = _resolve_db_url()
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLAlchemyBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
