"""TU-25 a TU-31: regras puras da apuração (sem banco e sem HTTP)."""

from datetime import date
from decimal import Decimal

from app.dto.apuracao_dto import LinhaApuracao
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.votacao_dto import ContagemVoto
from app.models.enums import Cargo, SituacaoCargo, TipoVoto
from app.services.apuracao_service import apurar_cargo, definir_mais_votado, percentual


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


def test_tu25_percentual_arredonda_meio_para_cima():
    """TU-25 / RN-76: 1/3 = 33.33; 2/3 = 66.67; sem votos válidos = 0.00."""
    assert percentual(1, 3) == Decimal("33.33")
    assert percentual(2, 3) == Decimal("66.67")
    assert percentual(0, 0) == Decimal("0.00")
    assert percentual(1, 8) == Decimal("12.50")
    assert percentual(1, 16) == Decimal("6.25")
    assert percentual(1, 200) == Decimal("0.50")
    assert percentual(1, 400) == Decimal("0.25")
    assert percentual(1, 800) == Decimal("0.13")  # 0.125 sobe: meio para cima


def test_tu26_candidato_sem_votos_aparece_e_ordena_por_votos_e_numero():
    """TU-26 / RN-75: todos aparecem; ordem por votos (decrescente) e depois por número."""
    candidaturas = [
        uma_candidatura(1, "30"),
        uma_candidatura(2, "10"),
        uma_candidatura(3, "20"),
        uma_candidatura(4, "40"),
    ]
    resultado = apurar_cargo(Cargo.PRESIDENTE, candidaturas, [nominais(1, 5), nominais(3, 5)])

    assert [(c.numero, c.votos) for c in resultado.candidatos] == [
        ("20", 5),
        ("30", 5),
        ("10", 0),
        ("40", 0),
    ]


def test_tu27_brancos_e_nulos_nao_entram_nos_validos():
    """TU-27 / RN-76: percentual só sobre nominais; brancos e nulos aparecem à parte."""
    candidaturas = [uma_candidatura(1, "10"), uma_candidatura(2, "20")]
    resultado = apurar_cargo(
        Cargo.PRESIDENTE, candidaturas, [nominais(1, 3), nominais(2, 1), brancos(4), nulos(2)]
    )

    assert resultado.votos_validos == 4
    assert resultado.brancos == 4
    assert resultado.nulos == 2
    assert resultado.total_votos == 10
    assert [c.percentual_validos for c in resultado.candidatos] == [
        Decimal("75.00"),
        Decimal("25.00"),
    ]


def test_tu28_mais_votado_unico_e_definido_por_maior_votacao():
    """TU-28 / RN-77: líder único → DEFINIDO, critério MAIOR_VOTACAO."""
    candidaturas = [uma_candidatura(1, "10"), uma_candidatura(2, "20")]
    resultado = apurar_cargo(Cargo.PRESIDENTE, candidaturas, [nominais(1, 2), nominais(2, 7)])

    assert resultado.situacao == SituacaoCargo.DEFINIDO
    assert resultado.criterio == "MAIOR_VOTACAO"
    assert resultado.mais_votado.numero == "20"


def test_tu29_empate_e_resolvido_pelo_mais_idoso():
    """TU-29 / RN-77: empate nos votos → vence quem nasceu antes (DESEMPATE_POR_IDADE)."""
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


def test_tu30_empate_com_mesma_data_de_nascimento_fica_sem_vencedor():
    """TU-30 / RN-77: empate persistente → EMPATE, sem mais votado."""
    mesma_data = date(1970, 1, 1)
    linhas = [uma_linha("10", 3, mesma_data), uma_linha("20", 3, mesma_data)]

    mais_votado, situacao, criterio = definir_mais_votado(linhas)

    assert mais_votado is None
    assert situacao == SituacaoCargo.EMPATE
    assert criterio is None


def test_tu31_so_brancos_e_nulos_da_sem_votos_validos():
    """TU-31 / RN-78: sem nominais → SEM_VOTOS_VALIDOS, mais votado nulo, todos com 0.00."""
    candidaturas = [uma_candidatura(1, "10"), uma_candidatura(2, "20")]
    resultado = apurar_cargo(Cargo.PRESIDENTE, candidaturas, [brancos(2), nulos(1)])

    assert resultado.situacao == SituacaoCargo.SEM_VOTOS_VALIDOS
    assert resultado.mais_votado is None
    assert resultado.criterio is None
    assert resultado.votos_validos == 0
    assert all(c.percentual_validos == Decimal("0.00") for c in resultado.candidatos)
    assert definir_mais_votado([]) == (None, SituacaoCargo.SEM_VOTOS_VALIDOS, None)
