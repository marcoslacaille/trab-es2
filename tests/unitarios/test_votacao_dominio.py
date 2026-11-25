"""TU-19 a TU-21: regras puras da votação (sem banco e sem HTTP)."""

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.compartilhado.dominio import Cargo
from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos
from app.eleicoes.dominio import CandidaturaDetalhada, EleicaoResumo, StatusEleicao
from app.votacao.dominio import (
    ModoEscolha,
    TipoVoto,
    resolver_escolha,
    validar_eleitor_apto,
    validar_pode_votar,
)

FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = date(2026, 11, 25)
ABERTURA = datetime(2026, 11, 25, 8, 0, tzinfo=FUSO)


def uma_eleicao(**sobrescritas) -> EleicaoResumo:
    """Eleição ABERTA de 25/11/2026, das 08:00 às 17:00."""
    dados = {
        "id": 7,
        "descricao": "Eleições Gerais 2026",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
        "status": StatusEleicao.ABERTA,
        "aberta_em": ABERTURA,
        "encerrada_em": None,
        "criado_em": datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    }
    dados.update(sobrescritas)
    return EleicaoResumo(**dados)


def uma_candidatura(id: int, numero: str, nome_urna: str) -> CandidaturaDetalhada:
    return CandidaturaDetalhada(
        id=id,
        eleicao_id=7,
        cargo=Cargo.PRESIDENTE,
        numero=numero,
        candidato_id=id,
        nome_urna=nome_urna,
        data_nascimento=date(1970, 1, 1),
        partido_id=1,
        partido_sigla="PAB",
        partido_numero=13,
    )


# ---------- TU-19 ----------


@pytest.mark.parametrize("status", [StatusEleicao.AGENDADA, StatusEleicao.ENCERRADA])
def test_tu19_eleicao_agendada_ou_encerrada_recusa_voto(status):
    """TU-19 / RN-51: só se vota em eleição ABERTA."""
    eleicao = uma_eleicao(status=status)
    with pytest.raises(ConflitoDeEstado) as erro:
        validar_pode_votar(eleicao, datetime(2026, 11, 25, 10, 0, tzinfo=FUSO))
    assert erro.value.codigo == "ELEICAO_NAO_ABERTA"
    assert erro.value.detalhes == {"status": status.value}


def test_tu19_depois_do_horario_de_encerramento_recusa_voto():
    """TU-19 / RN-52: janela encerrada e o Chefe ainda não encerrou (17:00 já é fora)."""
    for hora in (time(17, 0), time(17, 1), time(23, 59)):
        with pytest.raises(ConflitoDeEstado) as erro:
            validar_pode_votar(uma_eleicao(), datetime.combine(HOJE, hora, tzinfo=FUSO))
        assert erro.value.codigo == "JANELA_ENCERRADA"


def test_tu19_no_dia_seguinte_recusa_voto():
    """TU-19 / RN-52: outro dia que não o da eleição, mesmo dentro do horário."""
    amanha = datetime(2026, 11, 26, 10, 0, tzinfo=FUSO)
    with pytest.raises(ConflitoDeEstado) as erro:
        validar_pode_votar(uma_eleicao(), amanha)
    assert erro.value.codigo == "JANELA_ENCERRADA"


def test_tu19_dentro_da_janela_passa():
    """TU-19 / RN-51 e RN-52: eleição ABERTA no dia e antes das 17:00 passa."""
    for hora in (time(8, 0), time(10, 0), time(16, 59, 59)):
        validar_pode_votar(uma_eleicao(), datetime.combine(HOJE, hora, tzinfo=FUSO))


# ---------- TU-20 ----------


def test_tu20_cadastrado_antes_da_abertura_e_apto():
    """TU-20 / RN-53: cadastrado antes da abertura passa."""
    validar_eleitor_apto(ABERTURA - timedelta(days=3), ABERTURA)


def test_tu20_cadastrado_no_mesmo_instante_da_abertura_e_apto():
    """TU-20 / RN-53: cadastrado exatamente no instante da abertura ainda passa."""
    validar_eleitor_apto(ABERTURA, ABERTURA)


def test_tu20_cadastrado_depois_da_abertura_e_recusado():
    """TU-20 / RN-53: um segundo depois da abertura já não é apto (403 ELEITOR_NAO_APTO)."""
    with pytest.raises(AcessoNegado) as erro:
        validar_eleitor_apto(ABERTURA + timedelta(seconds=1), ABERTURA)
    assert erro.value.codigo == "ELEITOR_NAO_APTO"


# ---------- TU-21 ----------

CANDIDATURAS = [uma_candidatura(1, "13", "Ana"), uma_candidatura(2, "45", "Bia")]


def test_tu21_numero_existente_vira_nominal():
    """TU-21 / RN-58: número de uma candidatura → NOMINAL, com os dados do candidato."""
    escolha = resolver_escolha(Cargo.PRESIDENTE, ModoEscolha.NUMERO, "45", CANDIDATURAS)
    assert escolha.tipo == TipoVoto.NOMINAL
    assert escolha.candidatura_id == 2
    assert (escolha.numero, escolha.nome_urna, escolha.partido_sigla) == ("45", "Bia", "PAB")


def test_tu21_numero_inexistente_vira_nulo():
    """TU-21 / RN-58: número válido para o cargo mas sem candidatura → NULO."""
    escolha = resolver_escolha(Cargo.PRESIDENTE, ModoEscolha.NUMERO, "99", CANDIDATURAS)
    assert escolha.tipo == TipoVoto.NULO
    assert escolha.candidatura_id is None
    assert escolha.nome_urna is None


def test_tu21_modo_branco_vira_branco_e_ignora_o_numero():
    """TU-21 / RN-58: modo BRANCO → BRANCO, sem candidatura, mesmo se vier número."""
    for numero in (None, "13"):
        escolha = resolver_escolha(Cargo.PRESIDENTE, ModoEscolha.BRANCO, numero, CANDIDATURAS)
        assert escolha.tipo == TipoVoto.BRANCO
        assert escolha.candidatura_id is None


@pytest.mark.parametrize("numero", [None, "", "1", "123", "01", "1a", "٣٣"])
def test_tu21_digitos_errados_dao_422(numero):
    """TU-21 / RN-58: número ausente, curto, longo, com zero à esquerda ou não ASCII → 422."""
    with pytest.raises(DadosInvalidos) as erro:
        resolver_escolha(Cargo.PRESIDENTE, ModoEscolha.NUMERO, numero, CANDIDATURAS)
    assert erro.value.codigo == "NUMERO_INVALIDO_PARA_CARGO"
    assert erro.value.detalhes == {"cargo": "PRESIDENTE", "digitos": 2}


def test_tu21_quantidade_de_digitos_depende_do_cargo():
    """TU-21 / RN-58: Senador exige 3 dígitos; 2 dígitos é 422 mesmo existindo em Presidente."""
    senadores = [replace(CANDIDATURAS[0], cargo=Cargo.SENADOR, numero="123")]
    with pytest.raises(DadosInvalidos):
        resolver_escolha(Cargo.SENADOR, ModoEscolha.NUMERO, "13", senadores)
    escolha = resolver_escolha(Cargo.SENADOR, ModoEscolha.NUMERO, "123", senadores)
    assert escolha.tipo == TipoVoto.NOMINAL
