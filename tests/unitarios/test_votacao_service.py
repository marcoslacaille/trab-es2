"""Testes do `VotacaoService`: as regras do voto e a orquestração, com tudo falso e sem banco."""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.cedula import emitir_cedula, ler_cedula
from app.core.exceptions import AcessoNegado, ConflitoDeEstado, DadosInvalidos, NaoEncontrado
from app.dto.candidatura_dto import CandidaturaDetalhada
from app.dto.eleicao_dto import EleicaoResumo
from app.dto.eleitor_dto import EleitorResumo
from app.dto.usuario_dto import UsuarioAutenticado
from app.dto.votacao_dto import CandidatoDaCedula, ComprovanteVoto, Escolha, PedidoRegistro
from app.models.enums import Cargo, ModoEscolha, Perfil, StatusEleicao, TipoVoto
from app.repositories.votacao_repository import VotacaoRepository
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService
from app.services.votacao_service import (
    FK_ELEITOR_DO_REGISTRO,
    VotacaoService,
    resolver_escolha,
    validar_eleitor_apto,
    validar_pode_votar,
)

FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = date(2026, 11, 25)
ABERTURA = datetime(2026, 11, 25, 8, 0, tzinfo=FUSO)
AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
PK_REGISTRO = "pk_registros_votacao"


def uma_eleicao(**sobrescritas) -> EleicaoResumo:
    """Eleição ABERTA de 25/11/2026, das 08:00 às 17:00."""
    dados = {
        "id": 7,
        "descricao": "Eleições Gerais 2026",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
        "status": StatusEleicao.ABERTA,
        "aberta_em": ABERTURA,
        "encerrada_em": None,
        "criado_em": datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    }
    dados.update(sobrescritas)
    return EleicaoResumo(**dados)


def uma_candidatura(id: int, numero: str, nome_urna: str) -> CandidaturaDetalhada:
    return CandidaturaDetalhada(
        id=id,
        eleicao_id=7,
        cargo=Cargo.PRESIDENTE,
        numero=numero,
        candidato_id=id,
        nome_urna=nome_urna,
        data_nascimento=date(1970, 1, 1),
        partido_id=1,
        partido_sigla="PAB",
        partido_numero=13,
    )


CANDIDATURAS = [uma_candidatura(1, "13", "Ana"), uma_candidatura(2, "45", "Bia")]
VOTO_NA_BIA = Escolha(
    TipoVoto.NOMINAL, candidatura_id=2, numero="45", nome_urna="Bia", partido_sigla="PAB"
)


def um_usuario() -> UsuarioAutenticado:
    return UsuarioAutenticado(id=5, nome="Ana Souza", cpf="52998224725", perfil=Perfil.ELEITOR)


def um_service() -> VotacaoService:
    """O service com tudo falso, já arrumado para um eleitor apto numa eleição aberta."""
    service = VotacaoService(
        sessao=Mock(),
        repository=Mock(spec=VotacaoRepository),
        eleicoes=Mock(spec=EleicaoService),
        eleitores=Mock(spec=EleitorService),
    )
    service.eleitores.obter_eleitor_do_usuario.return_value = EleitorResumo(
        id=11, usuario_id=5, criado_em=ABERTURA - timedelta(days=3)
    )
    service.eleicoes.obter_eleicao.return_value = uma_eleicao()
    service.eleicoes.obter_eleicao_para_votacao.return_value = uma_eleicao()
    service.eleicoes.listar_candidaturas.return_value = CANDIDATURAS
    service.repository.ja_votou.return_value = False
    return service


def um_erro_de_integridade(restricao: str | None) -> IntegrityError:
    """Um `IntegrityError` como o do PostgreSQL: o nome da restrição vem em `orig.diag`."""
    original = Exception("violação")
    original.diag = SimpleNamespace(constraint_name=restricao)
    return IntegrityError("INSERT ...", {}, original)


def uma_cedula(usuario_id: int = 5, eleicao_id: int = 7) -> str:
    """Uma cédula verdadeira: voto no número 45 para Presidente."""
    token, _ = emitir_cedula(usuario_id, eleicao_id, Cargo.PRESIDENTE, VOTO_NA_BIA, AGORA)
    return token


# --- regras puras -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "horas", "codigo"),
    [
        pytest.param(
            [StatusEleicao.AGENDADA, StatusEleicao.ENCERRADA],
            [time(10, 0)],
            "ELEICAO_NAO_ABERTA",
            id="eleicao-fora-de-aberta",
        ),
        pytest.param(
            [StatusEleicao.ABERTA],
            [time(17, 0), time(17, 1), time(23, 59)],
            "JANELA_ENCERRADA",
            id="depois-do-horario-de-encerramento",
        ),
        pytest.param(
            [StatusEleicao.ABERTA],
            [time(8, 0), time(10, 0), time(16, 59, 59)],
            None,
            id="dentro-da-janela",
        ),
    ],
)
def test_voto_so_na_eleicao_aberta_e_dentro_da_janela(status, horas, codigo):
    """RN-51 e RN-52: só se vota com a eleição ABERTA, no dia e antes do horário de encerramento."""
    for situacao in status:
        for hora in horas:
            eleicao = uma_eleicao(status=situacao)
            agora = datetime.combine(HOJE, hora, tzinfo=FUSO)
            if codigo is None:
                validar_pode_votar(eleicao, agora)
                continue
            with pytest.raises(ConflitoDeEstado) as erro:
                validar_pode_votar(eleicao, agora)
            assert erro.value.codigo == codigo, (situacao, hora)
            if codigo == "ELEICAO_NAO_ABERTA":
                assert erro.value.detalhes == {"status": situacao.value}


@pytest.mark.parametrize(
    ("depois_da_abertura", "apto"),
    [
        pytest.param(timedelta(0), True, id="no-instante-da-abertura"),
        pytest.param(timedelta(seconds=1), False, id="um-segundo-depois"),
    ],
)
def test_eleitor_so_e_apto_se_cadastrado_ate_a_abertura(depois_da_abertura, apto):
    """RN-53: cadastrado até o instante da abertura (inclusive) vota; um segundo depois, 403."""
    cadastrado_em = ABERTURA + depois_da_abertura
    if apto:
        validar_eleitor_apto(cadastrado_em, ABERTURA)
        return

    with pytest.raises(AcessoNegado) as erro:
        validar_eleitor_apto(cadastrado_em, ABERTURA)

    assert erro.value.codigo == "ELEITOR_NAO_APTO"


@pytest.mark.parametrize(
    ("modo", "numero", "esperada"),
    [
        pytest.param(ModoEscolha.NUMERO, "45", VOTO_NA_BIA, id="numero-de-candidatura"),
        pytest.param(ModoEscolha.NUMERO, "99", Escolha(TipoVoto.NULO), id="numero-sem-candidatura"),
        pytest.param(ModoEscolha.BRANCO, "13", Escolha(TipoVoto.BRANCO), id="modo-branco"),
    ],
)
def test_resolver_escolha_vira_nominal_nulo_ou_branco(modo, numero, esperada):
    """RN-58: número de candidatura é NOMINAL, outro número é NULO, e o modo BRANCO é BRANCO."""
    assert resolver_escolha(Cargo.PRESIDENTE, modo, numero, CANDIDATURAS) == esperada


# --- o que o service pede ao repository e quando faz commit --------------------------------


def test_registrar_voto_nao_grava_nem_faz_commit():
    """RN-56 e RN-58: a prévia traz a cédula assinada, mas nada é gravado e não há commit."""
    service = um_service()
    pedido = PedidoRegistro(cargo=Cargo.PRESIDENTE, modo=ModoEscolha.NUMERO, numero="45")

    previa = service.registrar_voto(um_usuario(), 7, pedido, AGORA)

    assert previa.tipo == TipoVoto.NOMINAL
    assert previa.candidato == CandidatoDaCedula("45", "Bia", "PAB")
    assert previa.expira_em == AGORA + timedelta(minutes=5)
    cedula = ler_cedula(previa.token_cedula, AGORA)
    assert (cedula.usuario_id, cedula.eleicao_id, cedula.candidatura_id) == (5, 7, 2)
    service.repository.inserir_registro.assert_not_called()
    service.repository.inserir_voto.assert_not_called()
    service.sessao.commit.assert_not_called()


def test_registrar_voto_no_cargo_ja_votado_responde_409():
    """RN-54: quem já votou no cargo recebe 409 `VOTO_JA_REGISTRADO`, antes de emitir a cédula."""
    service = um_service()
    service.repository.ja_votou.return_value = True
    pedido = PedidoRegistro(cargo=Cargo.PRESIDENTE, modo=ModoEscolha.BRANCO)

    with pytest.raises(ConflitoDeEstado) as erro:
        service.registrar_voto(um_usuario(), 7, pedido, AGORA)

    assert erro.value.codigo == "VOTO_JA_REGISTRADO"
    service.repository.ja_votou.assert_called_once_with(11, 7, Cargo.PRESIDENTE)
    service.eleicoes.listar_candidaturas.assert_not_called()


def test_registrar_voto_em_cargo_sem_candidaturas_responde_422():
    """RN-55: cargo que a eleição não disputa dá 422 `CARGO_NAO_DISPUTADO`."""
    service = um_service()
    service.eleicoes.listar_candidaturas.return_value = []
    pedido = PedidoRegistro(cargo=Cargo.SENADOR, modo=ModoEscolha.BRANCO)

    with pytest.raises(DadosInvalidos) as erro:
        service.registrar_voto(um_usuario(), 7, pedido, AGORA)

    assert erro.value.codigo == "CARGO_NAO_DISPUTADO"
    assert erro.value.detalhes == {"cargo": "SENADOR"}


def test_confirmar_voto_grava_registro_e_voto_e_faz_commit():
    """RN-56 e RN-60: grava quem votou e o voto, sem ligação entre si, num único commit."""
    service = um_service()
    passos = []
    service.repository.inserir_registro.side_effect = lambda *argumentos: passos.append("registro")
    service.repository.inserir_voto.side_effect = lambda *argumentos: passos.append("voto")
    service.sessao.commit.side_effect = lambda: passos.append("commit")

    comprovante = service.confirmar_voto(um_usuario(), 7, uma_cedula(), AGORA)

    assert passos == ["registro", "voto", "commit"]
    # O registro sabe quem votou e em qual cargo; o voto sabe o que foi votado, mas não quem votou.
    service.repository.inserir_registro.assert_called_once_with(11, 7, Cargo.PRESIDENTE)
    service.repository.inserir_voto.assert_called_once_with(
        7, Cargo.PRESIDENTE, TipoVoto.NOMINAL, 2
    )
    service.eleicoes.obter_eleicao_para_votacao.assert_called_once_with(7)
    assert comprovante == ComprovanteVoto(
        eleicao_id=7, cargo=Cargo.PRESIDENTE, mensagem="Voto confirmado."
    )


def test_confirmar_voto_com_cedula_de_outro_eleitor_ou_eleicao_responde_422():
    """RN-57: a cédula só vale para o eleitor e a eleição de origem (`CEDULA_INVALIDA`)."""
    service = um_service()
    cedulas = {
        "de-outro-eleitor": uma_cedula(usuario_id=99),
        "de-outra-eleicao": uma_cedula(eleicao_id=8),
    }

    for origem, token in cedulas.items():
        with pytest.raises(DadosInvalidos) as erro:
            service.confirmar_voto(um_usuario(), 7, token, AGORA)

        assert erro.value.codigo == "CEDULA_INVALIDA", origem
    assert service.repository.mock_calls == []
    service.sessao.commit.assert_not_called()


def test_confirmar_voto_repetido_responde_409_e_desfaz_a_transacao():
    """RN-54 e RN-59: a chave primária violada vira `VOTO_JA_REGISTRADO` e há rollback."""
    service = um_service()
    service.repository.inserir_registro.side_effect = um_erro_de_integridade(PK_REGISTRO)

    with pytest.raises(ConflitoDeEstado) as erro:
        service.confirmar_voto(um_usuario(), 7, uma_cedula(), AGORA)

    assert erro.value.codigo == "VOTO_JA_REGISTRADO"
    service.sessao.rollback.assert_called_once_with()
    service.repository.inserir_voto.assert_not_called()
    service.sessao.commit.assert_not_called()


def test_confirmar_voto_com_o_eleitor_excluido_no_meio_responde_404():
    """Eleitor excluído entre a leitura e a gravação: a FK recusa, há rollback e vira 404."""
    service = um_service()
    service.repository.inserir_registro.side_effect = um_erro_de_integridade(FK_ELEITOR_DO_REGISTRO)

    with pytest.raises(NaoEncontrado) as erro:
        service.confirmar_voto(um_usuario(), 7, uma_cedula(), AGORA)

    assert erro.value.codigo == "ELEITOR_NAO_ENCONTRADO"
    service.sessao.rollback.assert_called_once_with()
    service.sessao.commit.assert_not_called()


def test_confirmar_voto_repassa_outra_violacao_sem_traduzir():
    """Restrição que o service não conhece sobe como veio, depois do rollback."""
    service = um_service()
    service.repository.inserir_voto.side_effect = um_erro_de_integridade("ck_votos_outra_regra")

    with pytest.raises(IntegrityError):
        service.confirmar_voto(um_usuario(), 7, uma_cedula(), AGORA)

    service.sessao.rollback.assert_called_once_with()
    service.sessao.commit.assert_not_called()


def test_voto_recusado_em_outro_dia_mesmo_com_a_eleicao_aberta():
    """RN-52: no dia seguinte, às 10:00, a eleição que o Chefe não encerrou recusa o voto."""
    amanha = datetime.combine(HOJE + timedelta(days=1), time(10, 0), tzinfo=FUSO)

    with pytest.raises(ConflitoDeEstado) as erro:
        validar_pode_votar(uma_eleicao(), amanha)

    assert erro.value.codigo == "JANELA_ENCERRADA"
