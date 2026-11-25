"""Relógio injetável: o horário do sistema é o de Brasília, com fuso."""

from datetime import UTC, datetime, timedelta

from app.core.relogio import agora, obter_agora


def test_agora_tem_fuso_de_sao_paulo():
    """`agora()` devolve um datetime com fuso, em America/Sao_Paulo (UTC-3)."""
    momento = agora()

    assert momento.tzinfo is not None
    assert momento.utcoffset() == timedelta(hours=-3)
    assert abs(momento - datetime.now(UTC)) < timedelta(seconds=5)
    # A dependência `obter_agora` é só um invólucro de `agora()`.
    assert abs(obter_agora() - agora()) < timedelta(seconds=5)
