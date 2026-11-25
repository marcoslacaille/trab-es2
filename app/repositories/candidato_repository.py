"""Repository de candidatos: consultas na tabela `candidatos`, sem commit."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidato import Candidato


class CandidatoRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_candidato_por_id(self, candidato_id: int) -> Candidato | None:
        return self.sessao.get(Candidato, candidato_id)

    def buscar_candidato_por_usuario_id(self, usuario_id: int) -> Candidato | None:
        consulta = select(Candidato).where(Candidato.usuario_id == usuario_id)
        return self.sessao.scalars(consulta).first()

    def buscar_candidatos_por_usuarios_ids(self, usuarios_ids: Iterable[int]) -> list[Candidato]:
        """Todos os candidatos desses usuários, numa única consulta."""
        consulta = select(Candidato).where(Candidato.usuario_id.in_(list(usuarios_ids)))
        return list(self.sessao.scalars(consulta))

    def buscar_candidatos_por_ids(self, ids: Iterable[int]) -> list[Candidato]:
        """Todos os candidatos com esses ids, numa única consulta."""
        return list(self.sessao.scalars(select(Candidato).where(Candidato.id.in_(list(ids)))))

    def inserir_candidato(self, candidato: Candidato) -> None:
        """Adiciona o candidato e faz `flush` para o banco gerar o `id` e conferir as restrições."""
        self.sessao.add(candidato)
        self.sessao.flush()

    def remover_candidato(self, candidato: Candidato) -> None:
        """Apaga o candidato e faz `flush`, para uma chave estrangeira violada aparecer já aqui."""
        self.sessao.delete(candidato)
        self.sessao.flush()
