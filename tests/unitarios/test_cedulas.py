"""TU-22 a TU-24: cédula cifrada (RN-57, RN-60, D-144)."""

import base64
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet

from app.compartilhado.dominio import Cargo
from app.core import cedula as modulo_cedula
from app.core.cedula import emitir_cedula, ler_cedula
from app.core.exceptions import DadosInvalidos
from app.core.security import criar_token_acesso
from app.identidade.dominio import Perfil
from app.votacao.dominio import Escolha, TipoVoto

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
NOMINAL = Escolha(TipoVoto.NOMINAL, candidatura_id=42, numero="13", nome_urna="Ana")


def _cifrar(dados: dict) -> str:
    """Monta uma cédula com a chave certa e o conteúdo escolhido pelo teste."""
    return modulo_cedula._cifrador().encrypt(json.dumps(dados).encode("utf-8")).decode("ascii")


def test_tu22_emitir_e_ler_devolve_os_mesmos_dados():
    """TU-22 / RN-57: a cédula lida traz exatamente o que foi emitido."""
    token, expira_em = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    cedula = ler_cedula(token, AGORA)
    assert (cedula.usuario_id, cedula.eleicao_id, cedula.cargo) == (5, 7, Cargo.PRESIDENTE)
    assert (cedula.tipo, cedula.candidatura_id) == (TipoVoto.NOMINAL, 42)
    assert expira_em == AGORA + timedelta(minutes=5)


def test_tu22_voto_branco_e_nulo_nao_tem_candidatura():
    """TU-22 / RN-57: BRANCO e NULO voltam com `candidatura_id` nulo."""
    for tipo in (TipoVoto.BRANCO, TipoVoto.NULO):
        token, _ = emitir_cedula(5, 7, Cargo.SENADOR, Escolha(tipo), AGORA)
        cedula = ler_cedula(token, AGORA)
        assert cedula.tipo == tipo
        assert cedula.candidatura_id is None


def test_tu23_ler_seis_minutos_depois_da_cedula_expirada():
    """TU-23 / RN-57: a validade usa o relógio injetável, não o relógio real."""
    token, _ = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    ler_cedula(token, AGORA + timedelta(minutes=4, seconds=59))  # ainda vale
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token, AGORA + timedelta(minutes=6))
    assert erro.value.codigo == "CEDULA_EXPIRADA"


def test_tu23_vale_ate_o_instante_exato_de_expira_em():
    """TU-23 / RN-57: com frações de segundo, a cédula vale até o `expira_em` informado."""
    com_fracao = AGORA.replace(microsecond=900_000)
    token, expira_em = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, com_fracao)
    ler_cedula(token, expira_em)  # ainda vale no instante informado ao eleitor
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token, expira_em + timedelta(microseconds=1))
    assert erro.value.codigo == "CEDULA_EXPIRADA"


def test_tu24_cedula_adulterada_e_invalida():
    """TU-24 / RN-57: trocar qualquer parte do token quebra a autenticação."""
    token, _ = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    meio = len(token) // 2
    adulterado = token[:meio] + ("A" if token[meio] != "A" else "B") + token[meio + 1 :]
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(adulterado, AGORA)
    assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_cedula_com_outra_chave_ou_lixo_e_invalida():
    """TU-24 / RN-57: cifrada com outra chave, ou texto qualquer, não é cédula."""
    falsa = Fernet(Fernet.generate_key()).encrypt(b'{"usuario_id": 5}').decode("ascii")
    for token in (falsa, "isto-nao-e-um-token", ""):
        with pytest.raises(DadosInvalidos) as erro:
            ler_cedula(token, AGORA)
        assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_token_de_acesso_no_lugar_da_cedula_e_invalido():
    """TU-24 / RN-57: o token de acesso não é uma cédula (chaves e formatos diferentes)."""
    token_de_acesso, _ = criar_token_acesso(5, Perfil.ELEITOR)
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token_de_acesso, AGORA)
    assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_cedula_com_campos_faltando_ou_errados_e_invalida():
    """TU-24 / RN-57: chave certa, mas sem `expira_em` ou com cargo desconhecido."""
    base = {
        "usuario_id": 5,
        "eleicao_id": 7,
        "cargo": "PRESIDENTE",
        "tipo": "BRANCO",
        "candidatura_id": None,
        "expira_em": (AGORA + timedelta(minutes=1)).isoformat(),
    }
    sem_expiracao = {chave: valor for chave, valor in base.items() if chave != "expira_em"}
    cargo_errado = {**base, "cargo": "PREFEITO"}
    for dados in (sem_expiracao, cargo_errado):
        with pytest.raises(DadosInvalidos) as erro:
            ler_cedula(_cifrar(dados), AGORA)
        assert erro.value.codigo == "CEDULA_INVALIDA"


def test_d144_cedula_nao_expoe_eleitor_nem_escolha():
    """D-144 / RN-60: sem a chave, o token não revela o eleitor, o cargo nem a escolha."""
    token, _ = emitir_cedula(987654, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    aberto = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    for revelador in (b"987654", b"candidatura_id", b"PRESIDENTE", b"NOMINAL", b"usuario"):
        assert revelador not in aberto
    assert not token.startswith("eyJ")  # não é mais um JWT legível
