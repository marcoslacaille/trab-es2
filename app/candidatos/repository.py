"""Repository: consultas só nas tabelas `candidatos` e `partidos`. Sem regra e sem commit."""

from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.candidatos.model import Candidato, Partido


def buscar_candidato_por_id(sessao: Session, candidato_id: int) -> Candidato | None:
    return sessao.get(Candidato, candidato_id)


def buscar_candidato_por_usuario_id(sessao: Session, usuario_id: int) -> Candidato | None:
    return sessao.scalars(select(Candidato).where(Candidato.usuario_id == usuario_id)).first()


def buscar_candidatos_por_usuarios_ids(
    sessao: Session, usuarios_ids: Iterable[int]
) -> list[Candidato]:
    """Todos os candidatos desses usuários, numa única consulta."""
    consulta = select(Candidato).where(Candidato.usuario_id.in_(list(usuarios_ids)))
    return list(sessao.scalars(consulta))


def buscar_candidatos_por_ids(sessao: Session, ids: Iterable[int]) -> list[Candidato]:
    """Todos os candidatos com esses ids, numa única consulta."""
    return list(sessao.scalars(select(Candidato).where(Candidato.id.in_(list(ids)))))


def inserir_candidato(sessao: Session, candidato: Candidato) -> None:
    """Adiciona o candidato e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
    sessao.add(candidato)
    sessao.flush()


def remover_candidato(sessao: Session, candidato: Candidato) -> None:
    """Apaga o candidato e faz `flush`, para uma chave estrangeira violada aparecer já aqui."""
    sessao.delete(candidato)
    sessao.flush()


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
