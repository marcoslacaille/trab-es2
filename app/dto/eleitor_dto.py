"""DTOs de eleitor: dados que passam entre controller, service e repository."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class EleitorResumo:
    """O mínimo que outros módulos precisam saber de um eleitor (usado por `votacao`)."""

    id: int
    usuario_id: int
    criado_em: datetime


@dataclass(frozen=True)
class EleitorDetalhado:
    """Dados do eleitor juntos com nome e CPF da credencial. Nunca traz a senha."""

    id: int
    usuario_id: int
    nome: str
    cpf: str
    titulo_eleitor: str
    data_nascimento: date
    criado_em: datetime


@dataclass(frozen=True)
class NovoEleitorDados:
    """Tudo o que o Chefe informa para cadastrar um eleitor (RN-20)."""

    nome: str
    cpf: str
    titulo_eleitor: str
    data_nascimento: date
    senha: str


@dataclass(frozen=True)
class AlteracoesEleitor:
    """O que pode mudar depois do cadastro: só nome, data de nascimento e senha (RN-23).

    Campo `None` significa "não alterar".
    """

    nome: str | None = None
    data_nascimento: date | None = None
    senha: str | None = None
