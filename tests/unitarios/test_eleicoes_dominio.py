from dataclasses import replace
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import ConflitoDeEstado, DadosInvalidos
from app.eleicoes.dominio import (
    EleicaoResumo,
    NovaEleicaoDados,
    StatusEleicao,
    links_da_eleicao,
    validar_abertura,
    validar_agendamento,
    validar_edicao,
    validar_encerramento,
)
from app.identidade.dominio import Perfil

FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = date(2026, 11, 25)
AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
UMA_CANDIDATURA = {Cargo.PRESIDENTE: 1}


def uma_eleicao(**sobrescritas) -> EleicaoResumo:
    """Eleição AGENDADA de 25/11/2026, 1º turno, das 08:00 às 17:00."""
    dados = {
        "id": 7,
        "descricao": "Eleições Gerais 2026 — 1º turno",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
        "status": StatusEleicao.AGENDADA,
        "aberta_em": None,
        "encerrada_em": None,
        "criado_em": datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    }
    dados.update(sobrescritas)
    return EleicaoResumo(**dados)


def uma_agenda(**sobrescritas) -> NovaEleicaoDados:
    dados = {
        "descricao": "Eleições Gerais 2026",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
    }
    dados.update(sobrescritas)
    return NovaEleicaoDados(**dados)


def abrir(eleicao=None, agora=AGORA, outra_aberta=False, candidaturas=UMA_CANDIDATURA):
    validar_abertura(eleicao or uma_eleicao(), agora, outra_aberta, candidaturas)


def codigo_do_erro(chamada) -> str:
    """Executa a chamada, que precisa levantar um erro de negócio, e devolve o código dele."""
    with pytest.raises((ConflitoDeEstado, DadosInvalidos)) as erro:
        chamada()
    return erro.value.codigo


# --- TU-13: agendamento -------------------------------------------------------------------


def test_tu13_aceita_agendamento_valido_e_data_de_hoje():
    """TU-13 / RN-11: data de hoje, janela correta e turno 1 ou 2 passam."""
    assert validar_agendamento(uma_agenda(), HOJE) == uma_agenda()
    assert validar_agendamento(uma_agenda(turno=2, data=date(2026, 12, 20)), HOJE)


def test_tu13_recusa_data_no_passado():
    """TU-13 / RN-11: data anterior a hoje dá `DATA_NO_PASSADO`."""
    agenda = uma_agenda(data=date(2026, 11, 24))

    assert codigo_do_erro(lambda: validar_agendamento(agenda, HOJE)) == "DATA_NO_PASSADO"


@pytest.mark.parametrize(
    ("abertura", "encerramento"),
    [(time(17, 0), time(8, 0)), (time(8, 0), time(8, 0))],
    ids=["invertida", "igual"],
)
def test_tu13_recusa_janela_invertida_ou_vazia(abertura, encerramento):
    """TU-13 / RN-11: a abertura precisa vir antes do encerramento (`JANELA_INVALIDA`)."""
    agenda = uma_agenda(horario_abertura=abertura, horario_encerramento=encerramento)

    assert codigo_do_erro(lambda: validar_agendamento(agenda, HOJE)) == "JANELA_INVALIDA"


@pytest.mark.parametrize("turno", [0, 3, -1])
def test_tu13_recusa_turno_diferente_de_1_e_2(turno):
    """TU-13 / RN-11: turno só pode ser 1 ou 2 (`DADOS_INVALIDOS`)."""
    assert codigo_do_erro(lambda: validar_agendamento(uma_agenda(turno=turno), HOJE)) == (
        "DADOS_INVALIDOS"
    )


@pytest.mark.parametrize("descricao", ["", "   ", "x" * 121])
def test_recusa_descricao_vazia_ou_longa_demais(descricao):
    """RN-11: a descrição, sem as pontas, tem de 1 a 120 caracteres."""
    agenda = uma_agenda(descricao=descricao)

    assert codigo_do_erro(lambda: validar_agendamento(agenda, HOJE)) == "DADOS_INVALIDOS"


def test_agendamento_devolve_a_descricao_sem_espacos_nas_pontas():
    """RN-11: os dados validados voltam normalizados."""
    assert validar_agendamento(uma_agenda(descricao="  Geral  "), HOJE).descricao == "Geral"


# --- TU-14: transições --------------------------------------------------------------------


@pytest.mark.parametrize("status", list(StatusEleicao))
def test_tu14_so_a_agendada_pode_ser_aberta(status):
    """TU-14 / RN-13: só AGENDADA → ABERTA passa; os outros status dão `TRANSICAO_INVALIDA`."""
    eleicao = uma_eleicao(status=status)

    if status == StatusEleicao.AGENDADA:
        abrir(eleicao)
    else:
        assert codigo_do_erro(lambda: abrir(eleicao)) == "TRANSICAO_INVALIDA"


@pytest.mark.parametrize("status", list(StatusEleicao))
def test_tu14_so_a_aberta_pode_ser_encerrada(status):
    """TU-14 / RN-13 / RN-18: só ABERTA → ENCERRADA passa; os outros dão `TRANSICAO_INVALIDA`."""
    if status == StatusEleicao.ABERTA:
        validar_encerramento(status)
    else:
        assert codigo_do_erro(lambda: validar_encerramento(status)) == "TRANSICAO_INVALIDA"


# --- TU-15: edição ------------------------------------------------------------------------


@pytest.mark.parametrize("status", list(StatusEleicao))
def test_tu15_so_a_agendada_pode_ser_editada(status):
    """TU-15 / RN-14: edição só em AGENDADA; os outros status dão `ELEICAO_NAO_EDITAVEL`."""
    if status == StatusEleicao.AGENDADA:
        validar_edicao(status)
    else:
        assert codigo_do_erro(lambda: validar_edicao(status)) == "ELEICAO_NAO_EDITAVEL"


# --- TU-16: abertura ----------------------------------------------------------------------


def test_tu16_abre_com_tudo_certo():
    """TU-16 / RN-15: na data, na janela, com candidatura e sem outra aberta, abre."""
    abrir()


def test_tu16_recusa_abrir_fora_da_data():
    """TU-16 / RN-15: outro dia que não o da eleição dá `FORA_DA_DATA`."""
    ontem = datetime(2026, 11, 24, 10, 0, tzinfo=FUSO)

    assert codigo_do_erro(lambda: abrir(agora=ontem)) == "FORA_DA_DATA"


def test_tu16_recusa_abrir_antes_do_horario_de_abertura():
    """TU-16 / RN-15: um minuto antes da abertura dá `FORA_DA_JANELA`."""
    cedo = datetime(2026, 11, 25, 7, 59, tzinfo=FUSO)

    assert codigo_do_erro(lambda: abrir(agora=cedo)) == "FORA_DA_JANELA"


def test_tu16_abre_exatamente_no_horario_de_abertura():
    """TU-16 / RN-15: o horário de abertura é inclusivo."""
    abrir(agora=datetime(2026, 11, 25, 8, 0, tzinfo=FUSO))


def test_tu16_recusa_abrir_exatamente_no_horario_de_encerramento():
    """TU-16 / RN-15: o horário de encerramento é exclusivo."""
    fim = datetime(2026, 11, 25, 17, 0, tzinfo=FUSO)

    assert codigo_do_erro(lambda: abrir(agora=fim)) == "FORA_DA_JANELA"


def test_tu16_recusa_abrir_com_outra_eleicao_aberta():
    """TU-16 / RN-16: só uma eleição aberta por vez (`OUTRA_ELEICAO_ABERTA`)."""
    assert codigo_do_erro(lambda: abrir(outra_aberta=True)) == "OUTRA_ELEICAO_ABERTA"


@pytest.mark.parametrize("candidaturas", [{}, {Cargo.PRESIDENTE: 0}])
def test_tu16_recusa_abrir_sem_candidaturas(candidaturas):
    """TU-16 / RN-15: sem nenhuma candidatura dá `SEM_CANDIDATURAS`."""
    assert codigo_do_erro(lambda: abrir(candidaturas=candidaturas)) == "SEM_CANDIDATURAS"


@pytest.mark.parametrize("quantidade", [1, 3])
def test_tu16_segundo_turno_exige_exatamente_dois_por_cargo(quantidade):
    """TU-16 / RN-17: 2º turno com 1 ou 3 candidaturas num cargo dá `SEGUNDO_TURNO_INCOMPLETO`."""
    eleicao = uma_eleicao(turno=2)
    candidaturas = {Cargo.PRESIDENTE: 2, Cargo.GOVERNADOR: quantidade}

    codigo = codigo_do_erro(lambda: abrir(eleicao, candidaturas=candidaturas))

    assert codigo == "SEGUNDO_TURNO_INCOMPLETO"


def test_tu16_segundo_turno_com_dois_por_cargo_abre():
    """TU-16 / RN-17: 2º turno com exatamente 2 por cargo disputado abre."""
    abrir(uma_eleicao(turno=2), candidaturas={Cargo.PRESIDENTE: 2, Cargo.GOVERNADOR: 2})


def test_primeiro_turno_aceita_qualquer_quantidade_por_cargo():
    """RN-17 só vale no 2º turno: o 1º aceita 1 ou 3 candidaturas."""
    abrir(candidaturas={Cargo.PRESIDENTE: 1, Cargo.SENADOR: 3})


def test_a_primeira_falha_e_a_devolvida_na_ordem_da_secao_9_5():
    """RN-13, 15 e 16: com tudo errado, o status vem antes de outra aberta, da data e da janela."""
    eleicao = uma_eleicao(status=StatusEleicao.ENCERRADA)
    outro_dia = datetime(2026, 11, 30, 20, 0, tzinfo=FUSO)

    codigo = codigo_do_erro(lambda: abrir(eleicao, outro_dia, True, {}))
    assert codigo == "TRANSICAO_INVALIDA"

    codigo = codigo_do_erro(lambda: abrir(uma_eleicao(), outro_dia, True, {}))
    assert codigo == "OUTRA_ELEICAO_ABERTA"

    codigo = codigo_do_erro(lambda: abrir(uma_eleicao(), outro_dia, False, {}))
    assert codigo == "FORA_DA_DATA"


# --- TU-18: links -------------------------------------------------------------------------

BASE = "/api/v1/eleicoes/7"
APURACAO = "/api/v1/apuracao/eleicoes/7"
LINK_SELF = ("self", "GET", BASE)

LINKS_ESPERADOS = {
    (Perfil.CHEFE_SECAO, StatusEleicao.AGENDADA): [
        LINK_SELF,
        ("editar", "PATCH", BASE),
        ("candidaturas", "GET", f"{BASE}/candidaturas"),
        ("nova-candidatura", "POST", f"{BASE}/candidaturas"),
        ("abrir", "POST", f"{BASE}/abertura"),
    ],
    (Perfil.CHEFE_SECAO, StatusEleicao.ABERTA): [
        LINK_SELF,
        ("encerrar", "POST", f"{BASE}/encerramento"),
        ("apuracao-parcial", "GET", f"{APURACAO}/parcial"),
    ],
    (Perfil.CHEFE_SECAO, StatusEleicao.ENCERRADA): [
        LINK_SELF,
        ("resultado", "GET", f"{APURACAO}/resultado"),
    ],
    (Perfil.ELEITOR, StatusEleicao.AGENDADA): [LINK_SELF],
    (Perfil.ELEITOR, StatusEleicao.ABERTA): [
        LINK_SELF,
        ("cedula", "GET", "/api/v1/votacao/eleicoes/7/cedula"),
        ("apuracao-parcial", "GET", f"{APURACAO}/parcial"),
    ],
    (Perfil.ELEITOR, StatusEleicao.ENCERRADA): [
        LINK_SELF,
        ("resultado", "GET", f"{APURACAO}/resultado"),
    ],
    (Perfil.CANDIDATO, StatusEleicao.AGENDADA): [LINK_SELF],
    (Perfil.CANDIDATO, StatusEleicao.ABERTA): [
        LINK_SELF,
        ("apuracao-parcial", "GET", f"{APURACAO}/parcial"),
    ],
    (Perfil.CANDIDATO, StatusEleicao.ENCERRADA): [
        LINK_SELF,
        ("resultado", "GET", f"{APURACAO}/resultado"),
    ],
}


@pytest.mark.parametrize(("perfil", "status"), list(LINKS_ESPERADOS))
def test_tu18_links_por_perfil_e_status(perfil, status):
    """TU-18 / RN-19: os links seguem a tabela da seção 9.5 em cada perfil × status."""
    eleicao = replace(uma_eleicao(), status=status)

    links = links_da_eleicao(eleicao, perfil)

    assert [(link.rel, link.metodo, link.href) for link in links] == LINKS_ESPERADOS[perfil, status]
