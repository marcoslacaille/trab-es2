"""Paginação padrão das listagens: o pedido (`Paginacao`) e o resultado (`Pagina`).

Não depende de framework, porque repositories e services o usam. Os parâmetros `pagina` e
`tamanho` da URL e o JSON da resposta ficam em `core/web.py`.
"""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class Pagina[T]:
    """Uma página de uma listagem: os itens e o total geral, para o cliente paginar."""

    itens: list[T]
    pagina: int
    tamanho: int
    total: int
