from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.core.relogio import obter_agora
from app.main import app
from tests.auxiliares import (  # noqa: F401  (registra as fixtures)
    cabecalho_candidato,
    cabecalho_chefe,
    cabecalho_eleitor,
)

TABELAS_DO_PUBLIC = """
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
"""


@pytest.fixture(scope="session", autouse=True)
def banco_migrado():
    """Recria o esquema uma vez por execução, com as migrações reais (constraints e trigger)."""
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def banco_limpo():
    """Cada teste começa com o banco vazio. TRUNCATE não dispara o trigger de imutabilidade.

    As tabelas são descobertas no próprio banco (todas do schema public, menos a
    alembic_version), então a fixture funciona mesmo quando ainda não existe nenhuma tabela.
    """
    with engine.begin() as conexao:
        tabelas = conexao.execute(text(TABELAS_DO_PUBLIC)).scalars().all()
        if tabelas:
            lista = ", ".join(f'"{tabela}"' for tabela in tabelas)
            conexao.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))


class RelogioDeTeste:
    def __init__(self, inicio: datetime):
        self.atual = inicio

    def __call__(self) -> datetime:
        return self.atual

    def avancar(self, **intervalo) -> None:
        self.atual += timedelta(**intervalo)


@pytest.fixture
def relogio():
    """Congela o tempo em 25/11/2026 às 10:00 (horário de Brasília)."""
    relogio = RelogioDeTeste(datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo")))
    app.dependency_overrides[obter_agora] = relogio
    yield relogio
    app.dependency_overrides.pop(obter_agora, None)


@pytest.fixture
def cliente(relogio):
    return TestClient(app)
