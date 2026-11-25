"""Cédula cifrada (RN-57, RN-60): emissão, leitura, validade e recusa do que não é cédula."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet

from app.core import cedula as modulo_cedula
from app.core.cedula import emitir_cedula, ler_cedula
from app.core.exceptions import DadosInvalidos
from app.core.security import criar_token_acesso
from app.dto.votacao_dto import Escolha
from app.models.enums import Cargo, Perfil, TipoVoto

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
NOMINAL = Escolha(TipoVoto.NOMINAL, candidatura_id=42, numero="13", nome_urna="Ana")


def _cifrar(dados: dict) -> str:
    """Monta uma cédula com a chave certa e o conteúdo escolhido pelo teste."""
    return modulo_cedula._cifrador().encrypt(json.dumps(dados).encode("utf-8")).decode("ascii")


def test_cedula_emitida_e_lida_devolve_os_mesmos_dados():
    """RN-57: a cédula lida traz o que foi emitido; voto em branco e nulo não têm candidatura."""
    token, expira_em = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    cedula = ler_cedula(token, AGORA)

    assert (cedula.usuario_id, cedula.eleicao_id, cedula.cargo) == (5, 7, Cargo.PRESIDENTE)
    assert (cedula.tipo, cedula.candidatura_id) == (TipoVoto.NOMINAL, 42)
    assert expira_em == AGORA + timedelta(minutes=5)
    for tipo in (TipoVoto.BRANCO, TipoVoto.NULO):
        token, _ = emitir_cedula(5, 7, Cargo.SENADOR, Escolha(tipo), AGORA)
        cedula = ler_cedula(token, AGORA)
        assert cedula.tipo == tipo
        assert cedula.candidatura_id is None


def test_cedula_expira_em_cinco_minutos():
    """RN-57: vale até o `expira_em` informado ao eleitor, pelo relógio injetável."""
    token, _ = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    ler_cedula(token, AGORA + timedelta(minutes=4, seconds=59))  # ainda vale
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token, AGORA + timedelta(minutes=6))
    assert erro.value.codigo == "CEDULA_EXPIRADA"

    # Com frações de segundo, o limite é o `expira_em` devolvido, e não um segundo arredondado.
    com_fracao = AGORA.replace(microsecond=900_000)
    token, expira_em = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, com_fracao)
    ler_cedula(token, expira_em)
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token, expira_em + timedelta(microseconds=1))
    assert erro.value.codigo == "CEDULA_EXPIRADA"


def _cedula_adulterada() -> list[str]:
    """Uma cédula verdadeira com um caractere trocado no meio."""
    token, _ = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    meio = len(token) // 2
    return [token[:meio] + ("A" if token[meio] != "A" else "B") + token[meio + 1 :]]


def _outra_chave_ou_lixo() -> list[str]:
    """O que não é cédula nossa: outra chave, texto qualquer, token de acesso e campos ruins."""
    base = {
        "usuario_id": 5,
        "eleicao_id": 7,
        "cargo": "PRESIDENTE",
        "tipo": "BRANCO",
        "candidatura_id": None,
        "expira_em": (AGORA + timedelta(minutes=1)).isoformat(),
    }
    sem_expiracao = {chave: valor for chave, valor in base.items() if chave != "expira_em"}
    token_de_acesso, _ = criar_token_acesso(5, Perfil.ELEITOR)
    return [
        Fernet(Fernet.generate_key()).encrypt(b'{"usuario_id": 5}').decode("ascii"),
        "isto-nao-e-um-token",
        "",
        token_de_acesso,
        _cifrar(sem_expiracao),
        _cifrar({**base, "cargo": "PREFEITO"}),
    ]


@pytest.mark.parametrize(
    "gerar_tokens",
    [_cedula_adulterada, _outra_chave_ou_lixo],
    ids=["adulterada", "outra-chave-ou-lixo"],
)
def test_cedula_invalida_e_recusada(gerar_tokens):
    """RN-57: mexer no token, ou usar o que não é cédula, dá `CEDULA_INVALIDA`."""
    for token in gerar_tokens():
        with pytest.raises(DadosInvalidos) as erro:
            ler_cedula(token, AGORA)
        assert erro.value.codigo == "CEDULA_INVALIDA", token
