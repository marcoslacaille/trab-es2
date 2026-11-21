"""Script `seed_demo`: cria o cenário da demonstração do zero e não duplica nada ao repetir."""

from sqlalchemy import text

from app.compartilhado.banco import SessionLocal
from app.scripts.seed_demo import semear


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
