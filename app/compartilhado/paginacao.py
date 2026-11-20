"""Paginação padrão das listagens: parâmetros de entrada e formato da resposta."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field


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
    pagina: Annotated[int, Query(ge=1, description="Número da página (começa em 1).")] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100, description="Itens por página (de 1 a 100).")] = 20,
) -> Paginacao:
    """Dependência FastAPI com `pagina` (≥ 1, padrão 1) e `tamanho` (1 a 100, padrão 20)."""
    return Paginacao(pagina=pagina, tamanho=tamanho)


class Pagina[T](BaseModel):
    """Resposta de toda listagem: os itens da página e o total geral para o cliente paginar."""

    itens: list[T]
    pagina: int = Field(description="Página devolvida (começa em 1).")
    tamanho: int = Field(description="Itens por página pedidos.")
    total: int = Field(description="Total de itens do filtro, somando todas as páginas.")
