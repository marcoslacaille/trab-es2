"""Consultas SQLAlchemy somente nas tabelas `candidatos` e `partidos`. Sem regra e sem commit."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.candidatos.modelos import Partido


def buscar_partido_por_id(sessao: Session, partido_id: int) -> Partido | None:
    return sessao.get(Partido, partido_id)


def existe_partido_com(sessao: Session, sigla: str, nome: str, numero: int) -> bool:
    """Já há um partido com esta sigla, este nome **ou** este número?"""
    consulta = (
        select(Partido.id)
        .where(or_(Partido.sigla == sigla, Partido.nome == nome, Partido.numero == numero))
        .limit(1)
    )
    return sessao.scalar(consulta) is not None


def listar_partidos_por_numero(sessao: Session) -> list[Partido]:
    return list(sessao.scalars(select(Partido).order_by(Partido.numero)))


def inserir_partido(sessao: Session, partido: Partido) -> None:
    """Adiciona o partido e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
    sessao.add(partido)
    sessao.flush()
