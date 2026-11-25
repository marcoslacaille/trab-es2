"""DTOs de eleição: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import date, datetime, time

from app.models.enums import StatusEleicao


@dataclass(frozen=True)
class EleicaoResumo:
    """A eleição como as rotas e os outros módulos a enxergam. Nunca é o objeto ORM."""

    id: int
    descricao: str
    data: date
    turno: int
    horario_abertura: time
    horario_encerramento: time
    status: StatusEleicao
    aberta_em: datetime | None
    encerrada_em: datetime | None
    criado_em: datetime


@dataclass(frozen=True)
class NovaEleicaoDados:
    """Tudo o que o Chefe informa para agendar uma eleição (RN-11)."""

    descricao: str
    data: date
    turno: int
    horario_abertura: time
    horario_encerramento: time


@dataclass(frozen=True)
class AlteracoesEleicao:
    """O que pode mudar enquanto a eleição está AGENDADA (RN-14). `None` = não alterar."""

    descricao: str | None = None
    data: date | None = None
    turno: int | None = None
    horario_abertura: time | None = None
    horario_encerramento: time | None = None
