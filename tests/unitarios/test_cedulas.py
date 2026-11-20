"""TU-22 a TU-24: cédula assinada (RN-57)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
import pytest

from app.compartilhado.config import obter_configuracao
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import DadosInvalidos
from app.identidade.dominio import Perfil
from app.identidade.tokens import criar_token_acesso
from app.votacao.cedulas import ALGORITMO, AUDIENCIA_CEDULA, emitir_cedula, ler_cedula
from app.votacao.dominio import Escolha, TipoVoto

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
NOMINAL = Escolha(TipoVoto.NOMINAL, candidatura_id=42, numero="13", nome_urna="Ana")


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


def test_tu24_cedula_adulterada_e_invalida():
    """TU-24 / RN-57: trocar qualquer parte do token quebra a assinatura."""
    token, _ = emitir_cedula(5, 7, Cargo.PRESIDENTE, NOMINAL, AGORA)
    cabecalho, corpo, assinatura = token.split(".")
    adulterado = f"{cabecalho}.{corpo}.{assinatura[:-2]}AA"
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(adulterado, AGORA)
    assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_cedula_com_outro_segredo_ou_lixo_e_invalida():
    """TU-24 / RN-57: assinada por outro segredo, ou texto qualquer, não é cédula."""
    segredo_falso = "outro-segredo-com-mais-de-32-caracteres!!"
    falsa = jwt.encode({"sub": "5", "aud": AUDIENCIA_CEDULA}, segredo_falso, ALGORITMO)
    for token in (falsa, "isto-nao-e-um-token", ""):
        with pytest.raises(DadosInvalidos) as erro:
            ler_cedula(token, AGORA)
        assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_token_de_acesso_no_lugar_da_cedula_e_invalido():
    """TU-24 / RN-57: a audiência separa o token de acesso da cédula."""
    token_de_acesso, _ = criar_token_acesso(5, Perfil.ELEITOR)
    with pytest.raises(DadosInvalidos) as erro:
        ler_cedula(token_de_acesso, AGORA)
    assert erro.value.codigo == "CEDULA_INVALIDA"


def test_tu24_cedula_assinada_com_campos_faltando_ou_errados_e_invalida():
    """TU-24 / RN-57: assinatura certa, mas sem `expira_em` ou com cargo desconhecido."""
    segredo = obter_configuracao().jwt_segredo
    base = {
        "sub": "5",
        "aud": AUDIENCIA_CEDULA,
        "eleicao_id": 7,
        "cargo": "PRESIDENTE",
        "tipo": "BRANCO",
        "candidatura_id": None,
        "expira_em": int(AGORA.timestamp()) + 60,
    }
    sem_expiracao = {chave: valor for chave, valor in base.items() if chave != "expira_em"}
    cargo_errado = {**base, "cargo": "PREFEITO"}
    for dados in (sem_expiracao, cargo_errado):
        token = jwt.encode(dados, segredo, algorithm=ALGORITMO)
        with pytest.raises(DadosInvalidos) as erro:
            ler_cedula(token, AGORA)
        assert erro.value.codigo == "CEDULA_INVALIDA"
