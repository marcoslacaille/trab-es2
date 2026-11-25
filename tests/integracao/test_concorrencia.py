"""TI-73, D-095, D-145 e D-146: concorrência no voto (RN-54) e entre voto e encerramento (RN-18)."""

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.apuracao import service as service_apuracao
from app.core import cedula
from app.core.database import SessionLocal
from app.core.exceptions import ConflitoDeEstado, NaoEncontrado
from app.dto.eleitor_dto import EleitorResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import Escolha
from app.eleicoes import repository as repository_eleicoes
from app.eleicoes import service as service_eleicoes
from app.models.enums import Cargo, Perfil, TipoVoto
from app.votacao import service
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
    token, _ = cedula.emitir_cedula(
        usuario_id, eleicao_id, Cargo.PRESIDENTE, Escolha(TipoVoto.BRANCO, None), agora
    )

    barreira = threading.Barrier(2)
    resultados: list[object] = []

    def confirmar() -> None:
        with SessionLocal() as sessao:
            barreira.wait(timeout=10)
            try:
                resultados.append(service.confirmar_voto(sessao, usuario, eleicao_id, token, agora))
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


def test_d095_encerramento_espera_a_confirmacao_em_andamento(cliente, cabecalho_chefe, relogio):
    """D-095 / RN-18: com uma confirmação segurando a trava, o encerramento só termina depois."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    terminou = threading.Event()
    resultados: list[object] = []

    def encerrar() -> None:
        with SessionLocal() as sessao:
            try:
                resultados.append(service_eleicoes.encerrar_eleicao(sessao, eleicao_id, agora))
            except Exception as erro:  # noqa: BLE001
                resultados.append(erro)
        terminou.set()

    with SessionLocal() as confirmacao:
        service_eleicoes.obter_eleicao_para_votacao(confirmacao, eleicao_id)  # FOR SHARE
        thread = threading.Thread(target=encerrar)
        thread.start()

        assert not terminou.wait(timeout=ESPERA_DE_BLOQUEIO)  # bloqueada pela trava

        confirmacao.commit()  # a confirmação termina e solta a trava
    assert terminou.wait(timeout=10)
    thread.join(timeout=10)

    assert len(resultados) == 1 and not isinstance(resultados[0], Exception), resultados
    with SessionLocal() as sessao:
        assert service_eleicoes.obter_eleicao(sessao, eleicao_id).status == "ENCERRADA"


def test_d095_confirmacao_espera_o_encerramento_e_depois_e_recusada(
    cliente, cabecalho_chefe, relogio
):
    """D-095 / RN-18: voto que chega durante o encerramento espera e é recusado (não entra)."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    usuario, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)
    terminou = threading.Event()
    resultados: list[object] = []

    def confirmar() -> None:
        with SessionLocal() as sessao:
            try:
                resultados.append(service.confirmar_voto(sessao, usuario, eleicao_id, token, agora))
            except Exception as erro:  # noqa: BLE001
                resultados.append(erro)
        terminou.set()

    with SessionLocal() as encerramento:
        eleicao = repository_eleicoes.obter_com_trava_exclusiva(encerramento, eleicao_id)
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
    with SessionLocal() as sessao:
        assert sessao.execute(text("SELECT COUNT(*) FROM votos")).scalar_one() == 0
        assert sessao.execute(text("SELECT COUNT(*) FROM registros_votacao")).scalar_one() == 0


def test_confirmacao_repassa_erro_de_integridade_desconhecido(
    cliente, cabecalho_chefe, relogio, monkeypatch
):
    """RN-54: só a violação da chave de `registros_votacao` vira VOTO_JA_REGISTRADO; outra sobe."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    usuario, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)

    def falhar(*argumentos, **nomeados):
        raise IntegrityError("INSERT ...", {}, Exception("violação desconhecida"))

    monkeypatch.setattr(service.repository, "inserir_voto", falhar)

    with SessionLocal() as sessao, pytest.raises(IntegrityError):
        service.confirmar_voto(sessao, usuario, eleicao_id, token, agora)
    with SessionLocal() as sessao:
        assert sessao.execute(text("SELECT COUNT(*) FROM registros_votacao")).scalar_one() == 0


def test_d145_eleitor_excluido_durante_a_confirmacao_da_404(
    cliente, cabecalho_chefe, relogio, monkeypatch
):
    """D-145 / RN-54: eleitor excluído no meio da confirmação → 404, sem gravar nada."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    usuario, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)
    # Simula a corrida: o eleitor foi lido, mas a linha já não existe quando o registro é gravado.
    sumido = EleitorResumo(id=999_999, usuario_id=usuario.id, criado_em=agora)
    monkeypatch.setattr(
        service.eleitores_service, "obter_eleitor_do_usuario", lambda sessao, usuario_id: sumido
    )

    with SessionLocal() as sessao, pytest.raises(NaoEncontrado) as erro:
        service.confirmar_voto(sessao, usuario, eleicao_id, token, agora)

    assert erro.value.codigo == "ELEITOR_NAO_ENCONTRADO"
    with SessionLocal() as sessao:
        assert sessao.execute(text("SELECT COUNT(*) FROM votos")).scalar_one() == 0
        assert sessao.execute(text("SELECT COUNT(*) FROM registros_votacao")).scalar_one() == 0


def test_d146_apuracao_le_votos_e_votantes_no_mesmo_instante(
    cliente, cabecalho_chefe, relogio, monkeypatch
):
    """D-146 / RN-74, RN-79: um voto confirmado no meio da apuração não aparece pela metade."""
    eleicao_id = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    agora = relogio()
    eleitor, token = _eleitor_com_cedula(cliente, cabecalho_chefe, eleicao_id, agora)
    contar_votos_original = service.contar_votos

    def contar_e_deixar_um_voto_entrar(sessao, eleicao):
        contagens = contar_votos_original(sessao, eleicao)
        with SessionLocal() as outra:  # outra requisição confirma um voto bem agora
            service.confirmar_voto(outra, eleitor, eleicao_id, token, agora)
        return contagens

    monkeypatch.setattr(service, "contar_votos", contar_e_deixar_um_voto_entrar)
    with SessionLocal() as sessao:
        durante = service_apuracao.apuracao_parcial(sessao, eleitor, eleicao_id, None, agora)
    monkeypatch.undo()
    with SessionLocal() as sessao:
        depois = service_apuracao.apuracao_parcial(sessao, eleitor, eleicao_id, None, agora)

    assert durante.comparecimento.votantes == 0  # mesmo instante da contagem: ainda sem votos
    assert sum(cargo.total_votos for cargo in durante.cargos) == 0
    assert depois.comparecimento.votantes == 1  # o voto entrou de verdade
    assert sum(cargo.total_votos for cargo in depois.cargos) == 1
