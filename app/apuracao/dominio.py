"""Regras puras da apuração: percentual, mais votado e montagem do resultado de um cargo.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.dto.apuracao_dto import LinhaApuracao, ResultadoCargo
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.votacao_dto import ContagemVoto
from app.models.enums import Cargo, SituacaoCargo, TipoVoto

CRITERIO_MAIOR_VOTACAO = "MAIOR_VOTACAO"
CRITERIO_DESEMPATE_POR_IDADE = "DESEMPATE_POR_IDADE"


def percentual(votos: int, validos: int) -> Decimal:
    """Percentual sobre votos válidos, 2 casas, meio para cima (RN-76)."""
    if validos == 0:
        return Decimal("0.00")
    return (Decimal(votos) * 100 / Decimal(validos)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def definir_mais_votado(
    linhas: list[LinhaApuracao],
) -> tuple[LinhaApuracao | None, SituacaoCargo, str | None]:
    """Linhas já ordenadas por votos. Empate: mais idoso; persistindo, EMPATE (RN-77, RN-78)."""
    if not linhas or linhas[0].votos == 0:
        return None, SituacaoCargo.SEM_VOTOS_VALIDOS, None
    lideres = [linha for linha in linhas if linha.votos == linhas[0].votos]
    if len(lideres) == 1:
        return lideres[0], SituacaoCargo.DEFINIDO, CRITERIO_MAIOR_VOTACAO
    nascimento_mais_antigo = min(linha.data_nascimento for linha in lideres)
    mais_idosos = [linha for linha in lideres if linha.data_nascimento == nascimento_mais_antigo]
    if len(mais_idosos) == 1:
        return mais_idosos[0], SituacaoCargo.DEFINIDO, CRITERIO_DESEMPATE_POR_IDADE
    return None, SituacaoCargo.EMPATE, None


def _separar_contagens(contagens: list[ContagemVoto]) -> tuple[int, int, dict[int, int]]:
    """Devolve (brancos, nulos, votos nominais por id de candidatura) de um cargo."""
    brancos = sum(c.total for c in contagens if c.tipo == TipoVoto.BRANCO)
    nulos = sum(c.total for c in contagens if c.tipo == TipoVoto.NULO)
    nominais = {
        c.candidatura_id: c.total
        for c in contagens
        if c.tipo == TipoVoto.NOMINAL and c.candidatura_id is not None
    }
    return brancos, nulos, nominais


def apurar_cargo(
    cargo: Cargo,
    candidaturas_do_cargo: list[CandidaturaDetalhada],
    contagens_do_cargo: list[ContagemVoto],
) -> ResultadoCargo:
    """Monta a apuração de um cargo (RN-75 a RN-78).

    Separa brancos e nulos dos nominais; cria uma linha por candidatura, inclusive com 0 votos;
    calcula os percentuais sobre os votos válidos (só os nominais); ordena por votos
    (decrescente) e depois por número; e decide o mais votado.
    """
    brancos, nulos, votos_por_candidatura = _separar_contagens(contagens_do_cargo)
    votos_validos = sum(votos_por_candidatura.values())

    linhas = [
        LinhaApuracao(
            numero=candidatura.numero,
            nome_urna=candidatura.nome_urna,
            partido_sigla=candidatura.partido_sigla,
            votos=votos_por_candidatura.get(candidatura.id, 0),
            percentual_validos=percentual(
                votos_por_candidatura.get(candidatura.id, 0), votos_validos
            ),
            data_nascimento=candidatura.data_nascimento,
        )
        for candidatura in candidaturas_do_cargo
    ]
    linhas.sort(key=lambda linha: (-linha.votos, linha.numero))
    mais_votado, situacao, criterio = definir_mais_votado(linhas)
    return ResultadoCargo(
        cargo=cargo,
        total_votos=votos_validos + brancos + nulos,
        votos_validos=votos_validos,
        brancos=brancos,
        nulos=nulos,
        situacao=situacao,
        criterio=criterio,
        mais_votado=mais_votado,
        candidatos=linhas,
    )
