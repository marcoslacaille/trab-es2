"""Consultas SQLAlchemy somente na tabela `usuarios`. Sem regra de negócio e sem commit."""

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compartilhado.paginacao import Paginacao
from app.identidade.modelos import Usuario


def buscar_por_id(sessao: Session, usuario_id: int) -> Usuario | None:
    return sessao.get(Usuario, usuario_id)


def buscar_por_cpf(sessao: Session, cpf: str) -> Usuario | None:
    return sessao.scalars(select(Usuario).where(Usuario.cpf == cpf)).first()


def buscar_por_ids(sessao: Session, ids: Iterable[int]) -> list[Usuario]:
    return list(sessao.scalars(select(Usuario).where(Usuario.id.in_(list(ids)))))


def inserir(sessao: Session, usuario: Usuario) -> None:
    """Adiciona o usuário e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
    sessao.add(usuario)
    sessao.flush()


def remover(sessao: Session, usuario: Usuario) -> None:
    sessao.delete(usuario)
    sessao.flush()


def listar(
    sessao: Session, perfil: str, nome: str | None, paginacao: Paginacao
) -> tuple[list[Usuario], int]:
    """Usuários do perfil, filtrados por parte do nome (sem diferenciar maiúsculas), por nome.

    Devolve a página pedida e o total de usuários que passam pelo filtro.
    """
    filtro = [Usuario.perfil == perfil]
    if nome:
        # `%` e `_` digitados pela pessoa valem como texto comum, não como curinga do LIKE.
        texto = nome.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filtro.append(Usuario.nome.ilike(f"%{texto}%", escape="\\"))

    total = sessao.scalar(select(func.count()).select_from(Usuario).where(*filtro)) or 0
    consulta = (
        select(Usuario)
        .where(*filtro)
        .order_by(Usuario.nome, Usuario.id)
        .limit(paginacao.tamanho)
        .offset(paginacao.deslocamento)
    )
    return list(sessao.scalars(consulta)), total
