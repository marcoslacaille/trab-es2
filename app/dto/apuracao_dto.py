"""DTOs de apuração: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import Cargo, SituacaoCargo, StatusEleicao


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
    """A apuração de um cargo."""

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
