"""Testes do `ApuracaoService`: regras da apuração e acesso por perfil, sem banco e sem HTTP."""

from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import AcessoNegado, ConflitoDeEstado
from app.dto.apuracao_dto import LinhaApuracao
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import ContagemVoto
from app.models.enums import Cargo, Perfil, SituacaoCargo, StatusEleicao, TipoVoto
from app.services.apuracao_service import (
    ApuracaoService,
    apurar_cargo,
    definir_mais_votado,
    percentual,
)
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService
from app.services.votacao_service import VotacaoService

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)


def uma_candidatura(id: int, numero: str, nascimento: date = date(1970, 1, 1)):
    return CandidaturaDetalhada(
        id=id,
        eleicao_id=1,
        cargo=Cargo.PRESIDENTE,
        numero=numero,
        candidato_id=id,
        nome_urna=f"Candidato {numero}",
        data_nascimento=nascimento,
        partido_id=1,
        partido_sigla="PT",
        partido_numero=int(numero[:2]),
    )


def nominais(candidatura_id: int, total: int) -> ContagemVoto:
    return ContagemVoto(Cargo.PRESIDENTE, TipoVoto.NOMINAL, candidatura_id, total)


def brancos(total: int) -> ContagemVoto:
    return ContagemVoto(Cargo.PRESIDENTE, TipoVoto.BRANCO, None, total)


def nulos(total: int) -> ContagemVoto:
    return ContagemVoto(Cargo.PRESIDENTE, TipoVoto.NULO, None, total)


def uma_linha(numero: str, votos: int, nascimento: date) -> LinhaApuracao:
    return LinhaApuracao(numero, f"Candidato {numero}", "PT", votos, Decimal("0.00"), nascimento)


def uma_eleicao(status: StatusEleicao) -> EleicaoResumo:
    return EleicaoResumo(
        id=1,
        descricao="Eleições Gerais 2026",
        data=date(2026, 11, 25),
        turno=1,
        horario_abertura=time(8, 0),
        horario_encerramento=time(17, 0),
        status=status,
        aberta_em=None if status == StatusEleicao.AGENDADA else AGORA,
        encerrada_em=None,
        criado_em=datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    )


def um_usuario(perfil: Perfil) -> UsuarioAutenticado:
    return UsuarioAutenticado(id=5, nome="Fulano de Tal", cpf="52998224725", perfil=perfil)


def um_service() -> ApuracaoService:
    """O service com tudo falso: o que ele decide é testado sem ler nada do banco."""
    return ApuracaoService(
        sessao=Mock(),
        votacao=Mock(spec=VotacaoService),
        eleicoes=Mock(spec=EleicaoService),
        eleitores=Mock(spec=EleitorService),
    )


# --- regras puras -------------------------------------------------------------------------


def test_percentual_arredonda_meio_para_cima():
    """RN-76: 1/3 = 33,33; 2/3 = 66,67; sem votos válidos = 0,00; o meio sobe (1/800 = 0,13)."""
    assert percentual(1, 3) == Decimal("33.33")
    assert percentual(2, 3) == Decimal("66.67")
    assert percentual(0, 0) == Decimal("0.00")
    assert percentual(1, 8) == Decimal("12.50")
    assert percentual(1, 16) == Decimal("6.25")
    assert percentual(1, 200) == Decimal("0.50")
    assert percentual(1, 400) == Decimal("0.25")
    assert percentual(1, 800) == Decimal("0.13")  # 0.125 sobe: meio para cima


def test_apurar_cargo_lista_todos_e_so_conta_votos_validos():
    """RN-75 e RN-76: todos aparecem, por votos e número; branco e nulo não são votos válidos."""
    candidaturas = [
        uma_candidatura(1, "30"),
        uma_candidatura(2, "10"),
        uma_candidatura(3, "20"),
        uma_candidatura(4, "40"),
    ]
    contagens = [nominais(1, 3), nominais(3, 3), nominais(2, 2), brancos(4), nulos(2)]

    resultado = apurar_cargo(Cargo.PRESIDENTE, candidaturas, contagens)

    assert [(c.numero, c.votos) for c in resultado.candidatos] == [
        ("20", 3),
        ("30", 3),
        ("10", 2),
        ("40", 0),  # sem votos, mas aparece
    ]
    assert [c.percentual_validos for c in resultado.candidatos] == [
        Decimal("37.50"),
        Decimal("37.50"),
        Decimal("25.00"),
        Decimal("0.00"),
    ]
    assert resultado.votos_validos == 8
    assert resultado.brancos == 4
    assert resultado.nulos == 2
    assert resultado.total_votos == 14


def test_empate_e_resolvido_pelo_mais_idoso():
    """RN-77: empate nos votos vence quem nasceu antes (`DESEMPATE_POR_IDADE`)."""
    candidaturas = [
        uma_candidatura(1, "10", date(1980, 5, 5)),
        uma_candidatura(2, "20", date(1960, 5, 5)),
        uma_candidatura(3, "30", date(1950, 1, 1)),
    ]
    resultado = apurar_cargo(
        Cargo.PRESIDENTE, candidaturas, [nominais(1, 4), nominais(2, 4), nominais(3, 1)]
    )

    assert resultado.situacao == SituacaoCargo.DEFINIDO
    assert resultado.criterio == "DESEMPATE_POR_IDADE"
    assert resultado.mais_votado.numero == "20"  # o 30 é mais idoso, mas não está empatado


def test_empate_persistente_fica_sem_mais_votado():
    """RN-77: empate com a mesma data de nascimento não tem vencedor (`EMPATE`)."""
    mesma_data = date(1970, 1, 1)
    linhas = [uma_linha("10", 3, mesma_data), uma_linha("20", 3, mesma_data)]

    mais_votado, situacao, criterio = definir_mais_votado(linhas)

    assert mais_votado is None
    assert situacao == SituacaoCargo.EMPATE
    assert criterio is None


def test_so_brancos_e_nulos_da_sem_votos_validos():
    """RN-78: sem votos nominais não há mais votado e todos os percentuais são 0,00."""
    candidaturas = [uma_candidatura(1, "10"), uma_candidatura(2, "20")]
    resultado = apurar_cargo(Cargo.PRESIDENTE, candidaturas, [brancos(2), nulos(1)])

    assert resultado.situacao == SituacaoCargo.SEM_VOTOS_VALIDOS
    assert resultado.mais_votado is None
    assert resultado.criterio is None
    assert resultado.votos_validos == 0
    assert all(c.percentual_validos == Decimal("0.00") for c in resultado.candidatos)
    assert definir_mais_votado([]) == (None, SituacaoCargo.SEM_VOTOS_VALIDOS, None)


# --- o que o service decide, com as dependências falsas -------------------------------------


def test_parcial_so_com_a_eleicao_aberta():
    """RN-70: a parcial só existe com a eleição ABERTA; encerrada, o erro aponta o resultado."""
    service = um_service()
    chefe = um_usuario(Perfil.CHEFE_SECAO)

    service.eleicoes.obter_eleicao.return_value = uma_eleicao(StatusEleicao.AGENDADA)
    with pytest.raises(ConflitoDeEstado) as agendada:
        service.apuracao_parcial(chefe, 1, None, AGORA)

    service.eleicoes.obter_eleicao.return_value = uma_eleicao(StatusEleicao.ENCERRADA)
    with pytest.raises(ConflitoDeEstado) as encerrada:
        service.apuracao_parcial(chefe, 1, None, AGORA)

    assert agendada.value.codigo == "APURACAO_INDISPONIVEL"
    assert agendada.value.detalhes == {"status": "AGENDADA"}
    assert encerrada.value.codigo == "APURACAO_INDISPONIVEL"
    assert encerrada.value.detalhes == {
        "status": "ENCERRADA",
        "resultado": "/api/v1/apuracao/eleicoes/1/resultado",
    }
    service.votacao.contar_votos.assert_not_called()


def test_candidato_so_ve_o_cargo_da_sua_candidatura():
    """RN-72: o Candidato é barrado sem candidatura na eleição e ao pedir outro cargo (403)."""
    service = um_service()
    service.eleicoes.obter_eleicao.return_value = uma_eleicao(StatusEleicao.ABERTA)
    candidato = um_usuario(Perfil.CANDIDATO)

    candidatura_de_outra_eleicao = replace(uma_candidatura(1, "13"), eleicao_id=2)
    service.eleicoes.candidaturas_do_usuario.return_value = [candidatura_de_outra_eleicao]
    with pytest.raises(AcessoNegado) as sem_candidatura:
        service.apuracao_parcial(candidato, 1, None, AGORA)

    service.eleicoes.candidaturas_do_usuario.return_value = [uma_candidatura(1, "13")]
    with pytest.raises(AcessoNegado) as outro_cargo:
        service.apuracao_parcial(candidato, 1, Cargo.GOVERNADOR, AGORA)

    assert sem_candidatura.value.codigo == "SEM_CANDIDATURA_NA_ELEICAO"
    assert outro_cargo.value.codigo == "CARGO_NAO_PERMITIDO"
    assert outro_cargo.value.detalhes == {"cargo_permitido": "PRESIDENTE"}
    service.votacao.contar_votos.assert_not_called()
