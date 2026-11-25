"""DTOs de partido: dados que passam entre controller, service e repository."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PartidoResumo:
    """Um partido como os outros módulos o enxergam (a candidatura guarda o `id`)."""

    id: int
    sigla: str
    nome: str
    numero: int


@dataclass(frozen=True)
class NovoPartidoDados:
    """Tudo o que o Chefe informa para cadastrar um partido (RN-32)."""

    sigla: str
    nome: str
    numero: int
