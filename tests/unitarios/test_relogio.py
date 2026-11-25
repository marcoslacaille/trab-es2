"""Relógio injetável: o horário do sistema é o de Brasília, com fuso."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import obter_configuracao
from app.core.relogio import agora, obter_agora


def test_agora_tem_fuso_de_sao_paulo():
    """`agora()` devolve um datetime no fuso da configuração (America/Sao_Paulo por padrão)."""
    momento = agora()

    assert momento.tzinfo is not None
    fuso = ZoneInfo(obter_configuracao().fuso_horario)
    assert momento.utcoffset() == fuso.utcoffset(momento.replace(tzinfo=None))
    assert abs(momento - datetime.now(UTC)) < timedelta(seconds=5)
    # A dependência `obter_agora` é só um invólucro de `agora()`.
    assert abs(obter_agora() - agora()) < timedelta(seconds=5)
