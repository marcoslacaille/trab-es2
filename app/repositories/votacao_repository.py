"""Repository de votação: consultas nas tabelas `registros_votacao` e `votos`, sem commit."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dto.votacao_dto import Comparecimento, ContagemVoto
from app.models.enums import Cargo, TipoVoto
from app.models.registro_votacao import RegistroVotacao
from app.models.voto import Voto


class VotacaoRepository:
    """As duas tabelas nunca são juntadas: nenhum método relaciona eleitor e escolha (RN-60)."""

    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def inserir_registro(self, eleitor_id: int, eleicao_id: int, cargo: Cargo) -> None:
        """Marca que o eleitor votou neste cargo. A chave primária impede o segundo (RN-54).

        Faz `flush` para a violação da chave aparecer aqui, e não só no commit.
        """
        self.sessao.add(
            RegistroVotacao(eleitor_id=eleitor_id, eleicao_id=eleicao_id, cargo=cargo.value)
        )
        self.sessao.flush()

    def inserir_voto(
        self,
        eleicao_id: int,
        cargo: Cargo,
        tipo: TipoVoto,
        candidatura_id: int | None,
    ) -> None:
        """Grava o voto, sem eleitor e sem horário. O `id` é um UUID aleatório (RN-60)."""
        self.sessao.add(
            Voto(
                eleicao_id=eleicao_id,
                cargo=cargo.value,
                tipo=tipo.value,
                candidatura_id=candidatura_id,
            )
        )
        self.sessao.flush()

    def ja_votou(self, eleitor_id: int, eleicao_id: int, cargo: Cargo) -> bool:
        """O eleitor já tem registro de voto neste cargo desta eleição?"""
        consulta = select(RegistroVotacao.eleitor_id).where(
            RegistroVotacao.eleitor_id == eleitor_id,
            RegistroVotacao.eleicao_id == eleicao_id,
            RegistroVotacao.cargo == cargo.value,
        )
        return self.sessao.scalars(consulta).first() is not None

    def cargos_votados(self, eleitor_id: int, eleicao_id: int) -> set[Cargo]:
        """Os cargos em que o eleitor já votou nesta eleição (RN-61). Nunca diz em quem."""
        consulta = select(RegistroVotacao.cargo).where(
            RegistroVotacao.eleitor_id == eleitor_id, RegistroVotacao.eleicao_id == eleicao_id
        )
        return {Cargo(cargo) for cargo in self.sessao.scalars(consulta)}

    def contar_votos(self, eleicao_id: int) -> list[ContagemVoto]:
        """`GROUP BY` cargo, tipo e candidatura: a apuração é calculada a cada consulta (RN-74)."""
        consulta = (
            select(Voto.cargo, Voto.tipo, Voto.candidatura_id, func.count())
            .where(Voto.eleicao_id == eleicao_id)
            .group_by(Voto.cargo, Voto.tipo, Voto.candidatura_id)
        )
        return [
            ContagemVoto(Cargo(cargo), TipoVoto(tipo), candidatura_id, total)
            for cargo, tipo, candidatura_id, total in self.sessao.execute(consulta)
        ]

    def contar_comparecimento(self, eleicao_id: int) -> Comparecimento:
        """Eleitores distintos que votaram e a contagem de registros por cargo."""
        distintos = self.sessao.scalar(
            select(func.count(func.distinct(RegistroVotacao.eleitor_id))).where(
                RegistroVotacao.eleicao_id == eleicao_id
            )
        )
        por_cargo = self.sessao.execute(
            select(RegistroVotacao.cargo, func.count())
            .where(RegistroVotacao.eleicao_id == eleicao_id)
            .group_by(RegistroVotacao.cargo)
        )
        return Comparecimento(distintos or 0, {Cargo(cargo): total for cargo, total in por_cargo})
