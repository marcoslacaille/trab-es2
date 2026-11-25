"""DTOs de candidato: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CandidatoResumo:
    """O mínimo que outros services precisam saber de um candidato (usado pelo `EleicaoService`).

    A data de nascimento serve ao desempate por idade da apuração (RN-77).
    """

    id: int
    usuario_id: int
    nome_urna: str
    data_nascimento: date


@dataclass(frozen=True)
class CandidatoDetalhado:
    """Dados do candidato juntos com nome e CPF da credencial. Nunca traz a senha."""

    id: int
    usuario_id: int
    nome: str
    nome_urna: str
    cpf: str
    data_nascimento: date
    criado_em: datetime


@dataclass(frozen=True)
class NovoCandidatoDados:
    """Tudo o que o Chefe informa para cadastrar um candidato (RN-31)."""

    nome: str
    nome_urna: str
    cpf: str
    data_nascimento: date
    senha: str


@dataclass(frozen=True)
class AlteracoesCandidato:
    """O que pode mudar depois do cadastro: nome, nome de urna, nascimento e senha (RN-31).

    Campo `None` significa "não alterar". O CPF nunca muda (RN-33).
    """

    nome: str | None = None
    nome_urna: str | None = None
    data_nascimento: date | None = None
    senha: str | None = None
