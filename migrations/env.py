from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.registro_modelos  # noqa: F401  (importar registra os modelos em Base.metadata)
from app.compartilhado.banco import Base
from app.compartilhado.config import obter_configuracao

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compara os modelos importados em registro_modelos com o banco.
target_metadata = Base.metadata

# A URL vem da configuração da aplicação (e não do alembic.ini). Nos testes, ela já aponta
# para o banco de teste.
URL_DO_BANCO = obter_configuracao().database_url


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem conectar no banco."""
    context.configure(
        url=URL_DO_BANCO,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações conectando no banco."""
    engine_das_migracoes = create_engine(URL_DO_BANCO, poolclass=pool.NullPool)

    with engine_das_migracoes.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
