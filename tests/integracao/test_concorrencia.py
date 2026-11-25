"""Concorrência no voto (RN-54), entre voto e encerramento (RN-18) e na apuração (RN-74, RN-79)."""

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core import cedula
from app.core.database import SessionLocal
from app.core.exceptions import ConflitoDeEstado
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import Escolha
from app.models.enums import Cargo, Perfil, TipoVoto
from app.repositories.eleicao_repository import EleicaoRepository
from app.services.apuracao_service import ApuracaoService
from app.services.eleicao_service import EleicaoService
from app.services.votacao_service import VotacaoService
from tests.auxiliares import SENHA_ELEITOR, eleicao_aberta_com_candidatos, login, novo_eleitor

ESPERA_DE_BLOQUEIO = 1.0  # segundos: tempo para provar que a outra thread continua bloqueada


def _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora):
    """Cadastra um eleitor e emite uma cédula BRANCO de PRESIDENTE. Devolve (usuario, token)."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()
    cabecalho = login(cliente, eleitor["cpf"], SENHA_ELEITOR)
    usuario_id = cliente.get("/api/v1/auth/me", headers=cabecalho).json()["id"]
    usuario = UsuarioAutenticado(
        id=usuario_id, nome=eleitor["nome"], cpf=eleitor["cpf"], perfil=Perfil.ELEITOR
    )
    token, _ = cedula.emitir_cedula(
        usuario_id, eleicao_id, Cargo.PRESIDENTE, Escolha(TipoVoto.BRANCO, None), agora
    )
    return usuario, token


def _contar(tabela: str) -> int:
    with SessionLocal() as sessao:
        return sessao.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar_one()


def test_duas_confirmacoes_simultaneas_geram_um_voto(cliente, cabecalho_chefe, relogio):
    """RN-54: duas threads confirmam a mesma cédula; um sucesso, um VOTO_JA_REGISTRADO."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = datetime(2026, 11, 25, 10, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    usuario, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)

    barreira = threading.Barrier(2)
    resultados: list[object] = []

    def confirmar() -> None:
        with SessionLocal() as sessao:
            barreira.wait(timeout=10)
            try:
                resultados.append(
                    VotacaoService(sessao).confirmar_voto(usuario, eleicao_id, token, agora)
                )
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
    assert _contar("votos") == 1
    assert _contar("registros_votacao") == 1


def test_encerramento_espera_a_confirmacao_em_andamento(cliente, cabecalho_chefe, relogio):
    """RN-18: a trava da eleição ordena o voto e o encerramento, nas duas direções."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()

    # 1) Com uma confirmação segurando a trava, o encerramento só termina depois dela.
    terminou = threading.Event()
    resultados: list[object] = []

    def encerrar() -> None:
        with SessionLocal() as sessao:
            try:
                resultados.append(EleicaoService(sessao).encerrar_eleicao(eleicao_id, agora))
            except Exception as erro:  # noqa: BLE001
                resultados.append(erro)
        terminou.set()

    with SessionLocal() as confirmacao:
        EleicaoService(confirmacao).obter_eleicao_para_votacao(eleicao_id)  # FOR SHARE
        thread = threading.Thread(target=encerrar)
        thread.start()

        assert not terminou.wait(timeout=ESPERA_DE_BLOQUEIO)  # bloqueada pela trava

        confirmacao.commit()  # a confirmação termina e solta a trava
    assert terminou.wait(timeout=10)
    thread.join(timeout=10)

    assert len(resultados) == 1 and not isinstance(resultados[0], Exception), resultados
    with SessionLocal() as sessao:
        assert EleicaoService(sessao).obter_eleicao(eleicao_id).status == "ENCERRADA"

    # 2) Voto que chega durante o encerramento espera e é recusado (não entra). Só há uma eleição
    # no teste, então o cenário volta a ABERTA direto no banco; nenhuma regra é contornada.
    with SessionLocal() as sessao:
        sessao.execute(
            text("UPDATE eleicoes SET status = 'ABERTA', encerrada_em = NULL WHERE id = :id"),
            {"id": eleicao_id},
        )
        sessao.commit()
    usuario, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)
    terminou = threading.Event()
    resultados = []

    def confirmar() -> None:
        with SessionLocal() as sessao:
            try:
                resultados.append(
                    VotacaoService(sessao).confirmar_voto(usuario, eleicao_id, token, agora)
                )
            except Exception as erro:  # noqa: BLE001
                resultados.append(erro)
        terminou.set()

    with SessionLocal() as encerramento:
        eleicao = EleicaoRepository(encerramento).obter_com_trava_exclusiva(eleicao_id)
        eleicao.status = "ENCERRADA"
        eleicao.encerrada_em = agora
        encerramento.flush()  # ainda sem commit: a trava exclusiva continua com esta sessão
        thread = threading.Thread(target=confirmar)
        thread.start()

        assert not terminou.wait(timeout=ESPERA_DE_BLOQUEIO)  # bloqueada pela trava

        encerramento.commit()
    assert terminou.wait(timeout=10)
    thread.join(timeout=10)

    assert len(resultados) == 1 and isinstance(resultados[0], ConflitoDeEstado), resultados
    assert resultados[0].codigo == "ELEICAO_NAO_ABERTA"
    assert _contar("votos") == 0
    assert _contar("registros_votacao") == 0


def test_apuracao_le_votos_e_votantes_no_mesmo_instante(
    cliente, cabecalho_chefe, relogio, monkeypatch
):
    """RN-74, RN-79: um voto confirmado no meio da apuração não aparece pela metade."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    eleitor, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)
    contar_votos_original = VotacaoService.contar_votos

    def contar_e_deixar_um_voto_entrar(self, eleicao):
        contagens = contar_votos_original(self, eleicao)
        with SessionLocal() as outra:  # outra requisição confirma um voto bem agora
            VotacaoService(outra).confirmar_voto(eleitor, eleicao_id, token, agora)
        return contagens

    monkeypatch.setattr(VotacaoService, "contar_votos", contar_e_deixar_um_voto_entrar)
    with SessionLocal() as sessao:
        durante = ApuracaoService(sessao).apuracao_parcial(eleitor, eleicao_id, None, agora)
    monkeypatch.undo()
    with SessionLocal() as sessao:
        depois = ApuracaoService(sessao).apuracao_parcial(eleitor, eleicao_id, None, agora)

    assert durante.comparecimento.votantes == 0  # mesmo instante da contagem: ainda sem votos
    assert sum(cargo.total_votos for cargo in durante.cargos) == 0
    assert depois.comparecimento.votantes == 1  # o voto entrou de verdade
    assert sum(cargo.total_votos for cargo in depois.cargos) == 1
