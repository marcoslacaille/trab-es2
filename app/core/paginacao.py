"""Paginação padrão das listagens: parâmetros de entrada e formato da resposta."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.validadores import MAIOR_ID

TAMANHO_MAXIMO = 100
# Maior página cujo deslocamento ((pagina - 1) * tamanho) cabe no BIGINT do OFFSET do banco,
# mesmo com o maior tamanho. Uma página maior nem chega ao banco (que daria 500).
MAIOR_PAGINA = MAIOR_ID // TAMANHO_MAXIMO


@dataclass(frozen=True)
class Paginacao:
    """Qual página de uma listagem o cliente pediu e de que tamanho."""

    pagina: int
    tamanho: int

    @property
    def deslocamento(self) -> int:
        """Quantos itens pular na consulta (OFFSET) para chegar ao início da página."""
        return (self.pagina - 1) * self.tamanho


def obter_paginacao(
    pagina: Annotated[
        int, Query(ge=1, le=MAIOR_PAGINA, description="Número da página (começa em 1).")
    ] = 1,
    tamanho: Annotated[
        int, Query(ge=1, le=TAMANHO_MAXIMO, description="Itens por página (de 1 a 100).")
    ] = 20,
) -> Paginacao:
    """Dependência FastAPI com `pagina` (1 a `MAIOR_PAGINA`, padrão 1) e `tamanho` (1 a 100).

    O teto de `pagina` evita que o deslocamento passe do BIGINT do banco (seria 500).
    """
    return Paginacao(pagina=pagina, tamanho=tamanho)


class Pagina[T](BaseModel):
    """Resposta de toda listagem: os itens da página e o total geral para o cliente paginar."""

    itens: list[T]
    pagina: int = Field(description="Página devolvida (começa em 1).")
    tamanho: int = Field(description="Itens por página pedidos.")
    total: int = Field(description="Total de itens do filtro, somando todas as páginas.")
