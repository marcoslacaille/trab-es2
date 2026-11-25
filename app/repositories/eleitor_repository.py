"""Repository de eleitores: consultas na tabela `eleitores`, sem commit."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.eleitor import Eleitor


class EleitorRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, eleitor_id: int) -> Eleitor | None:
        return self.sessao.get(Eleitor, eleitor_id)

    def buscar_por_titulo(self, titulo_eleitor: str) -> Eleitor | None:
        consulta = select(Eleitor).where(Eleitor.titulo_eleitor == titulo_eleitor)
        return self.sessao.scalars(consulta).first()

    def buscar_por_usuario_id(self, usuario_id: int) -> Eleitor | None:
        return self.sessao.scalars(select(Eleitor).where(Eleitor.usuario_id == usuario_id)).first()

    def buscar_por_usuarios_ids(self, usuarios_ids: Iterable[int]) -> list[Eleitor]:
        """Todos os eleitores desses usuários, numa única consulta."""
        consulta = select(Eleitor).where(Eleitor.usuario_id.in_(list(usuarios_ids)))
        return list(self.sessao.scalars(consulta))

    def inserir(self, eleitor: Eleitor) -> None:
        """Adiciona o eleitor e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
        self.sessao.add(eleitor)
        self.sessao.flush()

    def remover(self, eleitor: Eleitor) -> None:
        """Apaga o eleitor e faz `flush`, para uma chave estrangeira violada aparecer já aqui."""
        self.sessao.delete(eleitor)
        self.sessao.flush()

    def contar_cadastrados_ate(self, ate: datetime) -> int:
        """Quantos eleitores foram cadastrados até o instante `ate` (inclusive)."""
        consulta = select(func.count()).select_from(Eleitor).where(Eleitor.criado_em <= ate)
        return self.sessao.scalar(consulta) or 0
