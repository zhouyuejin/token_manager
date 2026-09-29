from logging.config import fileConfig

from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.script import ScriptDirectory

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.core.database import Base
from app.core.config import settings
from app.models import *  # noqa
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

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
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        app_tables = tables - {"alembic_version"}
        has_version_table = inspector.has_table("alembic_version")
        has_version = has_version_table and connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).first()
        if not has_version:
            if not app_tables:
                Base.metadata.create_all(bind=connection)
            else:
                missing_tables = {table.name for table in Base.metadata.sorted_tables} - tables
                missing_columns = {
                    table.name: {column.name for column in table.columns} -
                    {column["name"] for column in inspect(connection).get_columns(table.name)}
                    for table in Base.metadata.sorted_tables
                    if table.name in tables
                }
                missing_columns = {name: columns for name, columns in missing_columns.items() if columns}
                if missing_tables or missing_columns:
                    raise RuntimeError(
                        "Existing database has no Alembic version and does not match the current schema; "
                        "back up and adopt it explicitly before starting the service."
                    )
            if not has_version_table:
                connection.exec_driver_sql(
                    "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
                )
            head = ScriptDirectory.from_config(config).get_current_head()
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": head})
            connection.commit()

        if connection.dialect.name == "mysql":
            inspector = inspect(connection)
            if not inspector.has_table("alembic_version"):
                connection.exec_driver_sql(
                    "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
                )
            elif inspector.get_columns("alembic_version")[0]["type"].length < 64:
                connection.exec_driver_sql(
                    "ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(64) NOT NULL"
                )
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
