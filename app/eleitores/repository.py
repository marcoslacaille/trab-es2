"""Repository: consultas só na tabela `eleitores`. Sem regra de negócio e sem commit."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.eleitores.model import Eleitor


def buscar_por_id(sessao: Session, eleitor_id: int) -> Eleitor | None:
    return sessao.get(Eleitor, eleitor_id)


def buscar_por_titulo(sessao: Session, titulo_eleitor: str) -> Eleitor | None:
    return sessao.scalars(select(Eleitor).where(Eleitor.titulo_eleitor == titulo_eleitor)).first()


def buscar_por_usuario_id(sessao: Session, usuario_id: int) -> Eleitor | None:
    return sessao.scalars(select(Eleitor).where(Eleitor.usuario_id == usuario_id)).first()


def buscar_por_usuarios_ids(sessao: Session, usuarios_ids: Iterable[int]) -> list[Eleitor]:
    """Todos os eleitores desses usuários, numa única consulta."""
    return list(sessao.scalars(select(Eleitor).where(Eleitor.usuario_id.in_(list(usuarios_ids)))))


def inserir(sessao: Session, eleitor: Eleitor) -> None:
    """Adiciona o eleitor e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
    sessao.add(eleitor)
    sessao.flush()


def remover(sessao: Session, eleitor: Eleitor) -> None:
    """Apaga o eleitor e faz `flush`, para uma chave estrangeira violada aparecer já aqui."""
    sessao.delete(eleitor)
    sessao.flush()


def contar_cadastrados_ate(sessao: Session, ate: datetime) -> int:
    """Quantos eleitores foram cadastrados até o instante `ate` (inclusive)."""
    consulta = select(func.count()).select_from(Eleitor).where(Eleitor.criado_em <= ate)
    return sessao.scalar(consulta) or 0
