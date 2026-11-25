"""Relógio injetável: toda data e hora do sistema vem daqui, para os testes poderem congelá-las."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import obter_configuracao


def agora() -> datetime:
    """Data e hora atuais no fuso da eleição (America/Sao_Paulo), com fuso (aware)."""
    return datetime.now(ZoneInfo(obter_configuracao().fuso_horario))


def obter_agora() -> datetime:
    """Dependência FastAPI. Os testes substituem esta função para congelar o tempo."""
    return agora()
