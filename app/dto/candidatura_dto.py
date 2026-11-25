"""DTOs de candidatura: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import date

from app.models.enums import Cargo


@dataclass(frozen=True)
class CandidaturaDetalhada:
    """Uma candidatura com os dados de exibição do candidato e do partido (seção 9.5).

    `partido_id` não está na lista da seção 9.5, mas o contrato "Criar candidatura" devolve o
    `id` do partido (D-066).
    """

    id: int
    eleicao_id: int
    cargo: Cargo
    numero: str
    candidato_id: int
    nome_urna: str
    data_nascimento: date
    partido_id: int
    partido_sigla: str
    partido_numero: int


@dataclass(frozen=True)
class NovaCandidaturaDados:
    """Tudo o que o Chefe informa para criar uma candidatura (RN-40)."""

    candidato_id: int
    partido_id: int
    cargo: Cargo
    numero: str


@dataclass(frozen=True)
class AlteracoesCandidatura:
    """O que pode mudar numa candidatura: cargo, número e partido. `None` = não alterar."""

    cargo: Cargo | None = None
    numero: str | None = None
    partido_id: int | None = None
