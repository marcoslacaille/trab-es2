"""Repositório da votação contra o banco real (RN-54, RN-61, RN-74).

Não há ID de TI no PLANO para estas funções; o serviço da votação as usa (D-082).
"""

from app.core.database import SessionLocal
from app.models.enums import Cargo, TipoVoto
from app.repositories.votacao_repository import VotacaoRepository
from tests.integracao.test_banco_restricoes import (
    inserir_candidatura,
    inserir_eleicao,
    inserir_eleitor,
)


def test_inserir_consultar_e_contar():
    """RN-54, RN-61 e RN-74: registros, cargos votados, contagem por GROUP BY e comparecimento."""
    with SessionLocal() as sessao:
        repositorio = VotacaoRepository(sessao)
        eleicao_id = inserir_eleicao(sessao, "2026-11-25", aberta=True)
        eleitor_id = inserir_eleitor(sessao)
        candidatura_id = inserir_candidatura(sessao, eleicao_id, "PRESIDENTE", "13", 1)

        assert not repositorio.ja_votou(eleitor_id, eleicao_id, Cargo.PRESIDENTE)
        assert repositorio.cargos_votados(eleitor_id, eleicao_id) == set()

        repositorio.inserir_registro(eleitor_id, eleicao_id, Cargo.PRESIDENTE)
        repositorio.inserir_registro(eleitor_id, eleicao_id, Cargo.SENADOR)
        for tipo, candidatura in [
            (TipoVoto.NOMINAL, candidatura_id),
            (TipoVoto.NOMINAL, candidatura_id),
            (TipoVoto.NULO, None),
        ]:
            repositorio.inserir_voto(eleicao_id, Cargo.PRESIDENTE, tipo, candidatura)
        repositorio.inserir_voto(eleicao_id, Cargo.SENADOR, TipoVoto.BRANCO, None)
        sessao.commit()

        assert repositorio.ja_votou(eleitor_id, eleicao_id, Cargo.PRESIDENTE)
        assert not repositorio.ja_votou(eleitor_id, eleicao_id, Cargo.GOVERNADOR)
        assert repositorio.cargos_votados(eleitor_id, eleicao_id) == {
            Cargo.PRESIDENTE,
            Cargo.SENADOR,
        }

        contagens = {
            (c.cargo, c.tipo, c.candidatura_id): c.total
            for c in repositorio.contar_votos(eleicao_id)
        }
        assert contagens == {
            (Cargo.PRESIDENTE, TipoVoto.NOMINAL, candidatura_id): 2,
            (Cargo.PRESIDENTE, TipoVoto.NULO, None): 1,
            (Cargo.SENADOR, TipoVoto.BRANCO, None): 1,
        }

        comparecimento = repositorio.contar_comparecimento(eleicao_id)
        assert comparecimento.eleitores_que_votaram == 1
        assert comparecimento.por_cargo == {Cargo.PRESIDENTE: 1, Cargo.SENADOR: 1}


def test_comparecimento_sem_votos_e_zero():
    """RN-74: eleição sem registros devolve zero eleitores e nenhum cargo."""
    with SessionLocal() as sessao:
        repositorio = VotacaoRepository(sessao)
        eleicao_id = inserir_eleicao(sessao, "2026-11-25", aberta=True)
        comparecimento = repositorio.contar_comparecimento(eleicao_id)
        assert comparecimento.eleitores_que_votaram == 0
        assert comparecimento.por_cargo == {}
        assert repositorio.contar_votos(eleicao_id) == []
