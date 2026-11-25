"""Regras puras da apuração: percentual, mais votado e montagem do resultado de um cargo.

Não importa FastAPI nem SQLAlchemy: tudo aqui roda sem banco e sem HTTP. Os tipos
`CandidaturaDetalhada` e `ContagemVoto` vêm dos `dominio.py` de `eleicoes` e `votacao` (D-098).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.eleicoes.dominio import CandidaturaDetalhada
from app.models.enums import Cargo, SituacaoCargo, StatusEleicao, TipoVoto
from app.votacao.dominio import ContagemVoto

CRITERIO_MAIOR_VOTACAO = "MAIOR_VOTACAO"
CRITERIO_DESEMPATE_POR_IDADE = "DESEMPATE_POR_IDADE"


@dataclass(frozen=True)
class LinhaApuracao:
    """Um candidato na apuração de um cargo.

    `data_nascimento` só serve para o desempate (RN-77) e nunca vai para a resposta da API.
    """

    numero: str
    nome_urna: str
    partido_sigla: str
    votos: int
    percentual_validos: Decimal
    data_nascimento: date


@dataclass(frozen=True)
class ResultadoCargo:
    """A apuração de um cargo (seção 10, "Apuração parcial e resultado final")."""

    cargo: Cargo
    total_votos: int
    votos_validos: int
    brancos: int
    nulos: int
    situacao: SituacaoCargo
    criterio: str | None
    mais_votado: LinhaApuracao | None
    candidatos: list[LinhaApuracao]


@dataclass(frozen=True)
class ComparecimentoEleicao:
    """Aptos, votantes e abstenção da eleição (RN-79)."""

    eleitores_aptos: int
    votantes: int
    abstencao: int


@dataclass(frozen=True)
class Apuracao:
    """O que `apuracao_parcial` e `resultado_final` devolvem (`tipo` é PARCIAL ou FINAL)."""

    eleicao_id: int
    tipo: str
    status_eleicao: StatusEleicao
    gerado_em: datetime
    comparecimento: ComparecimentoEleicao
    cargos: list[ResultadoCargo]


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
