"""Casos de uso de candidatos e partidos. É a única porta de entrada do módulo para os outros.

As funções chamadas pelas rotas fazem `commit` no final.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.candidatos import repositorio
from app.candidatos.dominio import NovoPartidoDados, PartidoResumo, validar_partido
from app.candidatos.modelos import Partido
from app.compartilhado.erros import ConflitoDeEstado


def _resumir_partido(partido: Partido) -> PartidoResumo:
    """Converte o modelo no resumo do domínio. O ORM não sai do módulo."""
    return PartidoResumo(
        id=partido.id, sigla=partido.sigla, nome=partido.nome, numero=partido.numero
    )


def criar_partido(sessao: Session, dados: NovoPartidoDados, agora: datetime) -> PartidoResumo:
    """Cadastra um partido e faz commit (RN-32).

    A sigla é gravada em maiúsculas. Sigla, nome ou número já existentes dão 409
    `PARTIDO_DUPLICADO`; dados fora do formato dão 422 `DADOS_INVALIDOS`.
    """
    dados = validar_partido(dados)
    if repositorio.existe_partido_com(sessao, dados.sigla, dados.nome, dados.numero):
        raise ConflitoDeEstado(
            "Já existe um partido com esta sigla, nome ou número.", codigo="PARTIDO_DUPLICADO"
        )
    partido = Partido(sigla=dados.sigla, nome=dados.nome, numero=dados.numero, criado_em=agora)
    repositorio.inserir_partido(sessao, partido)
    sessao.commit()
    return _resumir_partido(partido)


def listar_partidos(sessao: Session) -> list[PartidoResumo]:
    """Todos os partidos, ordenados por número (RN-30: qualquer usuário logado pode listar)."""
    return [_resumir_partido(partido) for partido in repositorio.listar_partidos_por_numero(sessao)]


def obter_partido(sessao: Session, partido_id: int) -> PartidoResumo | None:
    """Devolve o partido ou `None` se não existir. Usada por `eleicoes` (RN-46)."""
    partido = repositorio.buscar_partido_por_id(sessao, partido_id)
    return _resumir_partido(partido) if partido else None
