import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base
import app.models


logger = logging.getLogger("uvicorn.error")
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    logger.info("migration.offline.begin")
    context.configure(
        url=config.get_main_option('sqlalchemy.url') or settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    logger.info("migration.offline.complete")


def run_migrations_online() -> None:
    connection = config.attributes.get('connection')
    if connection is not None:
        logger.info("migration.existing_connection.begin")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        logger.info("migration.existing_connection.complete")
        return

    database_url = config.get_main_option('sqlalchemy.url') or settings.database_url
    connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {'connect_timeout': 10}
    logger.info("migration.connection.begin dialect=%s", database_url.split(':', 1)[0])
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            logger.info("migration.connection.established")
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                logger.info("migration.apply.begin")
                context.run_migrations()
                logger.info("migration.apply.complete")
    finally:
        engine.dispose()
        logger.info("migration.connection.closed")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
