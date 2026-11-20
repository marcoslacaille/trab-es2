"""Regras puras de eleitores: dados que o serviço devolve e recebe, e validações (sem banco)."""

from dataclasses import dataclass
from datetime import date, datetime

from app.compartilhado.erros import DadosInvalidos
from app.compartilhado.validadores import calcular_idade, so_digitos

IDADE_MINIMA_ELEITOR = 16
DIGITOS_DO_TITULO = 12


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


def validar_idade_eleitor(data_nascimento: date, hoje: date) -> None:
    """RN-22: o eleitor precisa ter nascido no passado e ter 16 anos completos em `hoje`.

    Levanta `DadosInvalidos` com o código `IDADE_MINIMA` (422) nos dois casos.
    """
    if data_nascimento >= hoje:
        raise DadosInvalidos("A data de nascimento deve estar no passado.", codigo="IDADE_MINIMA")
    if calcular_idade(data_nascimento, hoje) < IDADE_MINIMA_ELEITOR:
        raise DadosInvalidos(
            f"O eleitor deve ter pelo menos {IDADE_MINIMA_ELEITOR} anos.", codigo="IDADE_MINIMA"
        )


def validar_titulo_eleitor(titulo_eleitor: str) -> None:
    """RN-21: o título tem exatamente 12 dígitos (0 a 9).

    Levanta `DadosInvalidos` com o código `DADOS_INVALIDOS` (422) se não tiver.
    """
    if len(titulo_eleitor) != DIGITOS_DO_TITULO or not so_digitos(titulo_eleitor):
        raise DadosInvalidos(
            f"O título de eleitor deve ter {DIGITOS_DO_TITULO} dígitos.",
            codigo="DADOS_INVALIDOS",
        )
