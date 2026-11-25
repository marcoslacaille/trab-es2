"""Repository de partidos: consultas na tabela `partidos`, sem commit."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.partido import Partido


class PartidoRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_partido_por_id(self, partido_id: int) -> Partido | None:
        return self.sessao.get(Partido, partido_id)

    def existe_partido_com(self, sigla: str, nome: str, numero: int) -> bool:
        """Já há um partido com esta sigla, este nome **ou** este número?"""
        consulta = (
            select(Partido.id)
            .where(or_(Partido.sigla == sigla, Partido.nome == nome, Partido.numero == numero))
            .limit(1)
        )
        return self.sessao.scalar(consulta) is not None

    def listar_partidos_por_numero(self) -> list[Partido]:
        return list(self.sessao.scalars(select(Partido).order_by(Partido.numero)))

    def inserir_partido(self, partido: Partido) -> None:
        """Adiciona o partido e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
        self.sessao.add(partido)
        self.sessao.flush()
