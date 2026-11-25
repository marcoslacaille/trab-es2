"""Script `seed_demo`: cria o cenário do zero, não duplica ao repetir e é atômico."""

from datetime import time

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.relogio import agora
from app.dto.eleicao_dto import NovaEleicaoDados
from app.models.enums import Perfil
from app.scripts.seed_demo import CHEFE_CPF, CHEFE_SENHA, semear
from app.services.eleicao_service import EleicaoService
from app.services.usuario_service import UsuarioService


def _contar(tabela: str) -> int:
    with SessionLocal() as sessao:
        return sessao.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar_one()


def test_semear_cria_o_cenario_e_repetir_nao_altera_nada(capsys):
    """Num banco vazio cria o cenário com eleição AGENDADA; a 2ª rodada sai com 1 sem alterar."""
    assert semear() == 0
    saida = capsys.readouterr().out
    assert "Dados de demonstração criados" in saida

    totais = {t: _contar(t) for t in ("usuarios", "partidos", "eleicoes", "candidaturas")}
    assert all(total > 0 for total in totais.values())
    with SessionLocal() as sessao:
        status = sessao.execute(text("SELECT status FROM eleicoes")).scalars().all()
    assert status == ["AGENDADA"]

    assert semear() == 1
    assert "já existem" in capsys.readouterr().out
    assert {t: _contar(t) for t in totais} == totais


def test_falha_no_meio_nao_grava_nada_e_permite_repetir(capsys):
    """Se uma regra barra o cenário no meio, nada fica gravado e dá para repetir depois."""
    with SessionLocal() as sessao:  # já existe uma eleição de 1º turno hoje: o seed vai esbarrar
        EleicaoService(sessao).criar_eleicao(
            NovaEleicaoDados(
                descricao="Eleição já cadastrada",
                data=agora().date(),
                turno=1,
                horario_abertura=time(8, 0),
                horario_encerramento=time(17, 0),
            ),
            agora(),
        )

    assert semear() == 2
    assert "ELEICAO_DUPLICADA" in capsys.readouterr().out
    assert {t: _contar(t) for t in ("usuarios", "partidos", "eleitores", "candidaturas")} == {
        "usuarios": 0,
        "partidos": 0,
        "eleitores": 0,
        "candidaturas": 0,
    }

    with SessionLocal() as sessao:  # o grupo resolve o conflito e roda de novo
        sessao.execute(text("DELETE FROM eleicoes"))
        sessao.commit()
    assert semear() == 0
    assert _contar("partidos") > 0


def test_semear_com_o_chefe_ja_criado_avisa_que_a_senha_e_a_do_env(capsys):
    """Com o Chefe criado antes (pelo `criar_chefe`, com outra senha), o seed não imprime a dele."""
    with SessionLocal() as sessao:
        UsuarioService(sessao).criar_credencial(
            CHEFE_CPF, "Chefe da Seção", "OutraSenha@1", Perfil.CHEFE_SECAO, agora()
        )
        sessao.commit()

    assert semear() == 0

    linha_do_chefe = next(
        linha for linha in capsys.readouterr().out.splitlines() if linha.startswith("Chefe ")
    )
    assert "já existia" in linha_do_chefe and CHEFE_SENHA not in linha_do_chefe


def test_semear_para_se_o_cpf_do_chefe_for_de_outro_perfil(capsys):
    """Se o CPF do Chefe da demonstração já é de um eleitor, o seed sai com 2 e não grava nada."""
    with SessionLocal() as sessao:
        UsuarioService(sessao).criar_credencial(
            CHEFE_CPF, "Eleitor Qualquer", "Eleitor@123", Perfil.ELEITOR, agora()
        )
        sessao.commit()

    assert semear() == 2
    assert "CPF_DO_CHEFE_EM_USO" in capsys.readouterr().out
    assert _contar("partidos") == 0
