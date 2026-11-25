"""Repository de usuários: consultas na tabela `usuarios`, sem commit."""

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.paginacao import Paginacao
from app.models.usuario import Usuario


class UsuarioRepository:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def buscar_por_id(self, usuario_id: int) -> Usuario | None:
        return self.sessao.get(Usuario, usuario_id)

    def buscar_por_cpf(self, cpf: str) -> Usuario | None:
        return self.sessao.scalars(select(Usuario).where(Usuario.cpf == cpf)).first()

    def buscar_por_ids(self, ids: Iterable[int]) -> list[Usuario]:
        return list(self.sessao.scalars(select(Usuario).where(Usuario.id.in_(list(ids)))))

    def inserir(self, usuario: Usuario) -> None:
        """Adiciona o usuário e faz `flush` para o banco gerar o `id` (e conferir as restrições)."""
        self.sessao.add(usuario)
        self.sessao.flush()

    def remover(self, usuario: Usuario) -> None:
        self.sessao.delete(usuario)
        self.sessao.flush()

    def listar(
        self, perfil: str, nome: str | None, paginacao: Paginacao
    ) -> tuple[list[Usuario], int]:
        """Usuários do perfil, filtrados por parte do nome (sem diferenciar maiúsculas), por nome.

        Devolve a página pedida e o total de usuários que passam pelo filtro.
        """
        filtro = [Usuario.perfil == perfil]
        if nome:
            # `%` e `_` digitados pela pessoa valem como texto comum, não como curinga do LIKE.
            texto = nome.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filtro.append(Usuario.nome.ilike(f"%{texto}%", escape="\\"))

        total = self.sessao.scalar(select(func.count()).select_from(Usuario).where(*filtro)) or 0
        consulta = (
            select(Usuario)
            .where(*filtro)
            .order_by(Usuario.nome, Usuario.id)
            .limit(paginacao.tamanho)
            .offset(paginacao.deslocamento)
        )
        return list(self.sessao.scalars(consulta)), total
