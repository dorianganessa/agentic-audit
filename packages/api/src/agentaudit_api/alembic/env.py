import os
from logging.config import fileConfig

from agentaudit_api.models import ApiKey, AuditEvent, Organization  # noqa: F401
from alembic import context
from sqlalchemy import create_engine
from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    return os.environ.get(
        "AGENTAUDIT_DATABASE_URL",
        config.get_main_option("sqlalchemy.url", ""),
    )


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
