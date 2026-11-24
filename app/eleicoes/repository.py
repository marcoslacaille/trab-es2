"""Consultas SQLAlchemy somente nas tabelas `eleicoes` e `candidaturas`. Sem regra e sem commit."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compartilhado.dominio import Cargo
from app.eleicoes.dominio import StatusEleicao
from app.eleicoes.model import Candidatura, Eleicao


def buscar_por_id(sessao: Session, eleicao_id: int) -> Eleicao | None:
    return sessao.get(Eleicao, eleicao_id)


def obter_com_trava_exclusiva(sessao: Session, eleicao_id: int) -> Eleicao | None:
    """`SELECT ... FOR UPDATE`: trava a linha da eleição até o fim da transação.

    Toda alteração no agregado começa por aqui, então duas alterações nunca se cruzam. Espera as
    travas compartilhadas das confirmações de voto em andamento terminarem (seção 9.5).
    """
    consulta = (
        select(Eleicao)
        .where(Eleicao.id == eleicao_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return sessao.scalars(consulta).first()


def obter_com_trava_compartilhada(sessao: Session, eleicao_id: int) -> Eleicao | None:
    """`SELECT ... FOR SHARE`: vários leitores seguram a linha juntos, mas ninguém a altera.

    Usada pela votação: enquanto um voto é confirmado, a eleição não pode ser encerrada.
    """
    consulta = (
        select(Eleicao)
        .where(Eleicao.id == eleicao_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    return sessao.scalars(consulta).first()


def existe_eleicao_aberta(sessao: Session) -> bool:
    """Há alguma eleição com status ABERTA?"""
    consulta = select(Eleicao.id).where(Eleicao.status == StatusEleicao.ABERTA.value).limit(1)
    return sessao.scalar(consulta) is not None


def existe_eleicao_na_data_e_turno(
    sessao: Session, data: date, turno: int, ignorando_id: int | None = None
) -> bool:
    """Já há uma eleição nesta data e turno? `ignorando_id` exclui a própria eleição na edição."""
    consulta = select(Eleicao.id).where(Eleicao.data == data, Eleicao.turno == turno)
    if ignorando_id is not None:
        consulta = consulta.where(Eleicao.id != ignorando_id)
    return sessao.scalar(consulta.limit(1)) is not None


def contar_candidaturas_por_cargo(sessao: Session, eleicao_id: int) -> dict[Cargo, int]:
    """Quantas candidaturas a eleição tem em cada cargo. Cargos sem candidatura ficam de fora."""
    consulta = (
        select(Candidatura.cargo, func.count())
        .where(Candidatura.eleicao_id == eleicao_id)
        .group_by(Candidatura.cargo)
    )
    return {Cargo(cargo): quantidade for cargo, quantidade in sessao.execute(consulta)}


def listar(sessao: Session, status: StatusEleicao | None) -> list[Eleicao]:
    """Todas as eleições (ou só as do status pedido), da mais antiga para a mais nova."""
    consulta = select(Eleicao).order_by(Eleicao.data, Eleicao.turno, Eleicao.id)
    if status is not None:
        consulta = consulta.where(Eleicao.status == status.value)
    return list(sessao.scalars(consulta))


def inserir(sessao: Session, eleicao: Eleicao) -> None:
    """Adiciona a eleição e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
    sessao.add(eleicao)
    sessao.flush()


def buscar_candidatura(sessao: Session, eleicao_id: int, candidatura_id: int) -> Candidatura | None:
    """A candidatura, se ela pertence a esta eleição."""
    consulta = select(Candidatura).where(
        Candidatura.id == candidatura_id, Candidatura.eleicao_id == eleicao_id
    )
    return sessao.scalars(consulta).first()


def listar_candidaturas(
    sessao: Session, eleicao_id: int, cargo: Cargo | None = None
) -> list[Candidatura]:
    """As candidaturas da eleição (ou só as do cargo pedido). A ordem final é do serviço."""
    consulta = select(Candidatura).where(Candidatura.eleicao_id == eleicao_id)
    if cargo is not None:
        consulta = consulta.where(Candidatura.cargo == cargo.value)
    return list(sessao.scalars(consulta))


def listar_candidaturas_do_candidato(sessao: Session, candidato_id: int) -> list[Candidatura]:
    """Todas as candidaturas de um candidato, em qualquer eleição."""
    consulta = select(Candidatura).where(Candidatura.candidato_id == candidato_id)
    return list(sessao.scalars(consulta))


def buscar_candidatura_por_numero(
    sessao: Session, eleicao_id: int, cargo: Cargo, numero: str
) -> Candidatura | None:
    """A candidatura que usa este número neste cargo da eleição, se houver."""
    consulta = select(Candidatura).where(
        Candidatura.eleicao_id == eleicao_id,
        Candidatura.cargo == cargo.value,
        Candidatura.numero == numero,
    )
    return sessao.scalars(consulta).first()


def contar_candidaturas_no_cargo(
    sessao: Session, eleicao_id: int, cargo: Cargo, ignorando_id: int | None = None
) -> int:
    """Quantas candidaturas o cargo tem na eleição (`ignorando_id` exclui a que está em edição)."""
    consulta = select(func.count()).where(
        Candidatura.eleicao_id == eleicao_id, Candidatura.cargo == cargo.value
    )
    if ignorando_id is not None:
        consulta = consulta.where(Candidatura.id != ignorando_id)
    return sessao.scalar(consulta) or 0


def existe_numero_no_cargo(
    sessao: Session,
    eleicao_id: int,
    cargo: Cargo,
    numero: str,
    ignorando_id: int | None = None,
) -> bool:
    """Já há candidatura com este número neste cargo da eleição (RN-43)?"""
    consulta = select(Candidatura.id).where(
        Candidatura.eleicao_id == eleicao_id,
        Candidatura.cargo == cargo.value,
        Candidatura.numero == numero,
    )
    if ignorando_id is not None:
        consulta = consulta.where(Candidatura.id != ignorando_id)
    return sessao.scalar(consulta.limit(1)) is not None


def existe_candidatura_do_candidato(sessao: Session, eleicao_id: int, candidato_id: int) -> bool:
    """O candidato já tem candidatura nesta eleição (RN-44)?"""
    consulta = select(Candidatura.id).where(
        Candidatura.eleicao_id == eleicao_id, Candidatura.candidato_id == candidato_id
    )
    return sessao.scalar(consulta.limit(1)) is not None


def inserir_candidatura(sessao: Session, candidatura: Candidatura) -> None:
    """Adiciona a candidatura e faz `flush` para o banco gerar o `id` e conferir as restrições."""
    sessao.add(candidatura)
    sessao.flush()


def remover_candidatura(sessao: Session, candidatura: Candidatura) -> None:
    """Apaga a candidatura e faz `flush`."""
    sessao.delete(candidatura)
    sessao.flush()
