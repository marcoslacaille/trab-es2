"""Consultas SQLAlchemy somente nas tabelas `registros_votacao` e `votos`. Sem regra e sem commit.

As duas tabelas nunca são juntadas: nenhuma função daqui relaciona eleitor e escolha (RN-60).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compartilhado.dominio import Cargo
from app.votacao.dominio import Comparecimento, ContagemVoto, TipoVoto
from app.votacao.model import RegistroVotacao, Voto


def inserir_registro(sessao: Session, eleitor_id: int, eleicao_id: int, cargo: Cargo) -> None:
    """Marca que o eleitor votou neste cargo. A chave primária impede o segundo (RN-54).

    Faz `flush` para a violação da chave aparecer aqui, e não só no commit.
    """
    sessao.add(RegistroVotacao(eleitor_id=eleitor_id, eleicao_id=eleicao_id, cargo=cargo.value))
    sessao.flush()


def inserir_voto(
    sessao: Session,
    eleicao_id: int,
    cargo: Cargo,
    tipo: TipoVoto,
    candidatura_id: int | None,
) -> None:
    """Grava o voto, sem eleitor e sem horário. O `id` é um UUID aleatório (RN-60)."""
    sessao.add(
        Voto(
            eleicao_id=eleicao_id,
            cargo=cargo.value,
            tipo=tipo.value,
            candidatura_id=candidatura_id,
        )
    )
    sessao.flush()


def ja_votou(sessao: Session, eleitor_id: int, eleicao_id: int, cargo: Cargo) -> bool:
    """O eleitor já tem registro de voto neste cargo desta eleição?"""
    consulta = select(RegistroVotacao.eleitor_id).where(
        RegistroVotacao.eleitor_id == eleitor_id,
        RegistroVotacao.eleicao_id == eleicao_id,
        RegistroVotacao.cargo == cargo.value,
    )
    return sessao.scalars(consulta).first() is not None


def cargos_votados(sessao: Session, eleitor_id: int, eleicao_id: int) -> set[Cargo]:
    """Os cargos em que o eleitor já votou nesta eleição (RN-61). Nunca diz em quem."""
    consulta = select(RegistroVotacao.cargo).where(
        RegistroVotacao.eleitor_id == eleitor_id, RegistroVotacao.eleicao_id == eleicao_id
    )
    return {Cargo(cargo) for cargo in sessao.scalars(consulta)}


def contar_votos(sessao: Session, eleicao_id: int) -> list[ContagemVoto]:
    """`GROUP BY` cargo, tipo e candidatura: a apuração é calculada a cada consulta (RN-74)."""
    consulta = (
        select(Voto.cargo, Voto.tipo, Voto.candidatura_id, func.count())
        .where(Voto.eleicao_id == eleicao_id)
        .group_by(Voto.cargo, Voto.tipo, Voto.candidatura_id)
    )
    return [
        ContagemVoto(Cargo(cargo), TipoVoto(tipo), candidatura_id, total)
        for cargo, tipo, candidatura_id, total in sessao.execute(consulta)
    ]


def contar_comparecimento(sessao: Session, eleicao_id: int) -> Comparecimento:
    """Eleitores distintos que votaram e a contagem de registros por cargo."""
    distintos = sessao.scalar(
        select(func.count(func.distinct(RegistroVotacao.eleitor_id))).where(
            RegistroVotacao.eleicao_id == eleicao_id
        )
    )
    por_cargo = sessao.execute(
        select(RegistroVotacao.cargo, func.count())
        .where(RegistroVotacao.eleicao_id == eleicao_id)
        .group_by(RegistroVotacao.cargo)
    )
    return Comparecimento(distintos or 0, {Cargo(cargo): total for cargo, total in por_cargo})
