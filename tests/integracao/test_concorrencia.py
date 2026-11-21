"""TI-73: duas confirmações simultâneas da mesma cédula geram um único voto (RN-54)."""

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.compartilhado.banco import SessionLocal
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import ConflitoDeEstado
from app.identidade.dominio import Perfil, UsuarioAutenticado
from app.votacao import cedulas, servico
from app.votacao.dominio import Escolha, TipoVoto
from tests.auxiliares import SENHA_ELEITOR, eleicao_aberta_com_candidatos, login, novo_eleitor


def test_ti73_duas_confirmacoes_simultaneas_geram_um_voto(cliente, cabecalho_chefe, relogio):
    """TI-73 / RN-54: duas threads confirmam a mesma cédula; um sucesso, um VOTO_JA_REGISTRADO."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()
    cabecalho = login(cliente, eleitor["cpf"], SENHA_ELEITOR)
    usuario_id = cliente.get("/api/v1/auth/me", headers=cabecalho).json()["id"]
    usuario = UsuarioAutenticado(
        id=usuario_id, nome=eleitor["nome"], cpf=eleitor["cpf"], perfil=Perfil.ELEITOR
    )

    agora = datetime(2026, 11, 25, 10, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    token, _ = cedulas.emitir_cedula(
        usuario_id, eleicao_id, Cargo.PRESIDENTE, Escolha(TipoVoto.BRANCO, None), agora
    )

    barreira = threading.Barrier(2)
    resultados: list[object] = []

    def confirmar() -> None:
        with SessionLocal() as sessao:
            barreira.wait(timeout=10)
            try:
                resultados.append(servico.confirmar_voto(sessao, usuario, eleicao_id, token, agora))
            except Exception as erro:  # noqa: BLE001  (o teste confere o tipo logo abaixo)
                resultados.append(erro)

    threads = [threading.Thread(target=confirmar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    conflitos = [r for r in resultados if isinstance(r, ConflitoDeEstado)]
    sucessos = [r for r in resultados if not isinstance(r, Exception)]
    assert len(resultados) == 2, resultados
    assert len(sucessos) == 1, resultados
    assert len(conflitos) == 1 and conflitos[0].codigo == "VOTO_JA_REGISTRADO", resultados
    with SessionLocal() as sessao:
        assert sessao.execute(text("SELECT COUNT(*) FROM votos")).scalar_one() == 1
        assert sessao.execute(text("SELECT COUNT(*) FROM registros_votacao")).scalar_one() == 1
