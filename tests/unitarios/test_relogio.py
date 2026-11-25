"""Relógio injetável: o horário do sistema é o de Brasília, com fuso (D-080)."""

from datetime import UTC, datetime, timedelta

from app.core.relogio import agora, obter_agora


def test_agora_tem_fuso_de_sao_paulo():
    """`agora()` devolve um datetime com fuso, em America/Sao_Paulo (UTC-3)."""
    momento = agora()

    assert momento.tzinfo is not None
    assert momento.utcoffset() == timedelta(hours=-3)
    assert abs(momento - datetime.now(UTC)) < timedelta(seconds=5)


def test_obter_agora_devolve_o_horario_atual():
    """A dependência `obter_agora` entrega o mesmo tipo de valor de `agora()`."""
    assert abs(obter_agora() - agora()) < timedelta(seconds=5)
