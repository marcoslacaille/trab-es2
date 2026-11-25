"""Testes do `EleicaoService`: as regras da eleição e da candidatura e a orquestração, sem banco."""

from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.dto.candidato_dto import CandidatoResumo
from app.dto.candidatura_dto import NovaCandidaturaDados
from app.dto.eleicao_dto import EleicaoResumo, NovaEleicaoDados
from app.models.candidatura import Candidatura
from app.models.eleicao import Eleicao
from app.models.enums import Cargo, StatusEleicao
from app.repositories.eleicao_repository import EleicaoRepository
from app.services.candidato_service import CandidatoService
from app.services.eleicao_service import (
    FK_CANDIDATO_DA_CANDIDATURA,
    EleicaoService,
    validar_abertura,
    validar_agendamento,
    validar_candidatura,
    validar_candidaturas_no_turno,
    validar_edicao,
    validar_encerramento,
)
from app.services.partido_service import PartidoService

FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = date(2026, 11, 25)
AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
UMA_CANDIDATURA = {Cargo.PRESIDENTE: 1}


def uma_eleicao(**sobrescritas) -> EleicaoResumo:
    """Eleição AGENDADA de 25/11/2026, 1º turno, das 08:00 às 17:00."""
    dados = {
        "id": 7,
        "descricao": "Eleições Gerais 2026 — 1º turno",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
        "status": StatusEleicao.AGENDADA,
        "aberta_em": None,
        "encerrada_em": None,
        "criado_em": datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    }
    dados.update(sobrescritas)
    return EleicaoResumo(**dados)


def uma_eleicao_gravada(**sobrescritas) -> Eleicao:
    """A mesma eleição como o repository a devolveria (a linha da tabela, em memória)."""
    dados = {
        "id": 7,
        "descricao": "Eleições Gerais 2026 — 1º turno",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
        "status": StatusEleicao.AGENDADA.value,
        "aberta_em": None,
        "encerrada_em": None,
        "criado_em": datetime(2026, 11, 1, 9, 0, tzinfo=FUSO),
    }
    dados.update(sobrescritas)
    return Eleicao(**dados)


def uma_agenda(**sobrescritas) -> NovaEleicaoDados:
    dados = {
        "descricao": "Eleições Gerais 2026",
        "data": HOJE,
        "turno": 1,
        "horario_abertura": time(8, 0),
        "horario_encerramento": time(17, 0),
    }
    dados.update(sobrescritas)
    return NovaEleicaoDados(**dados)


def um_service() -> EleicaoService:
    """O service com repository, candidatos, partidos e sessão falsos: nada chega ao banco."""
    return EleicaoService(
        sessao=Mock(),
        repository=Mock(spec=EleicaoRepository),
        candidatos=Mock(spec=CandidatoService),
        partidos=Mock(spec=PartidoService),
    )


def abrir(eleicao=None, agora=AGORA, outra_aberta=False, candidaturas=UMA_CANDIDATURA):
    validar_abertura(eleicao or uma_eleicao(), agora, outra_aberta, candidaturas)


def erro_de(chamada, *argumentos, **nomeados):
    """Executa a chamada, que precisa levantar um erro de negócio, e devolve o erro."""
    with pytest.raises((ConflitoDeEstado, DadosInvalidos)) as erro:
        chamada(*argumentos, **nomeados)
    return erro.value


def codigo_do_erro(chamada, *argumentos, **nomeados) -> str:
    return erro_de(chamada, *argumentos, **nomeados).codigo


def abrir_no_status(status: StatusEleicao) -> None:
    abrir(uma_eleicao(status=status))


# --- agendamento --------------------------------------------------------------------------


def test_agendamento_valido_e_aceito():
    """RN-11: data de hoje, janela correta e turno 1 ou 2 passam; a descrição perde as pontas."""
    assert validar_agendamento(uma_agenda(), HOJE) == uma_agenda()
    assert validar_agendamento(uma_agenda(turno=2, data=date(2026, 12, 20)), HOJE)
    assert validar_agendamento(uma_agenda(descricao="  Geral  "), HOJE).descricao == "Geral"


@pytest.mark.parametrize(
    "recusas",
    [
        pytest.param(
            [({"data": date(2026, 11, 24)}, "DATA_NO_PASSADO"), ({"turno": 3}, "DADOS_INVALIDOS")],
            id="data-no-passado-e-turno-3",
        ),
        pytest.param(
            [
                (
                    {"horario_abertura": time(17, 0), "horario_encerramento": time(8, 0)},
                    "JANELA_INVALIDA",
                ),
                (
                    {"horario_encerramento": time(8, 0)},
                    "JANELA_INVALIDA",
                ),  # abertura = encerramento
                ({"descricao": "  "}, "DADOS_INVALIDOS"),
            ],
            id="janela-invalida-e-descricao-vazia",
        ),
    ],
)
def test_agendamento_invalido_e_recusado(recusas):
    """RN-11: data anterior a hoje, janela invertida ou vazia, turno e descrição fora da regra."""
    for mudancas, codigo in recusas:
        recebido = codigo_do_erro(validar_agendamento, uma_agenda(**mudancas), HOJE)

        assert recebido == codigo, mudancas


# --- transições e edição ------------------------------------------------------------------


@pytest.mark.parametrize(
    "regras",
    [
        pytest.param([(abrir_no_status, StatusEleicao.AGENDADA, "TRANSICAO_INVALIDA")], id="abrir"),
        pytest.param(
            [
                (validar_encerramento, StatusEleicao.ABERTA, "TRANSICAO_INVALIDA"),
                (validar_edicao, StatusEleicao.AGENDADA, "ELEICAO_NAO_EDITAVEL"),
            ],
            id="encerrar-e-editar",
        ),
    ],
)
def test_transicao_e_edicao_so_no_status_certo(regras):
    """RN-13, RN-14 e RN-18: só a AGENDADA abre e edita, só a ABERTA encerra; o resto dá 409."""
    for validar, status_certo, codigo in regras:
        for status in StatusEleicao:
            if status == status_certo:
                validar(status)
            else:
                assert codigo_do_erro(validar, status) == codigo, (validar.__name__, status)


# --- abertura -----------------------------------------------------------------------------


def test_abertura_valida_e_aceita():
    """RN-15 e RN-17: no dia, na janela, com candidatura e sem outra eleição aberta."""
    abrir()
    abrir(agora=datetime(2026, 11, 25, 8, 0, tzinfo=FUSO))  # o horário de abertura é inclusivo
    abrir(uma_eleicao(turno=2), candidaturas={Cargo.PRESIDENTE: 2, Cargo.GOVERNADOR: 2})


@pytest.mark.parametrize(
    ("instantes", "codigo"),
    [
        pytest.param([datetime(2026, 11, 24, 10, 0, tzinfo=FUSO)], "FORA_DA_DATA", id="outro-dia"),
        pytest.param(
            [
                datetime(2026, 11, 25, 7, 59, tzinfo=FUSO),
                datetime(2026, 11, 25, 17, 0, tzinfo=FUSO),
            ],
            "FORA_DA_JANELA",
            id="antes-da-abertura-e-no-encerramento",
        ),
    ],
)
def test_abertura_recusada_fora_da_data_ou_da_janela(instantes, codigo):
    """RN-15: só no dia da eleição, e o horário de encerramento é exclusivo."""
    for agora in instantes:
        assert codigo_do_erro(abrir, uma_eleicao(), agora) == codigo, agora


@pytest.mark.parametrize(
    ("pedidos", "codigo"),
    [
        pytest.param([{"outra_aberta": True}], "OUTRA_ELEICAO_ABERTA", id="outra-aberta"),
        pytest.param(
            [{"candidaturas": {}}, {"candidaturas": {Cargo.PRESIDENTE: 0}}],
            "SEM_CANDIDATURAS",
            id="sem-candidaturas",
        ),
    ],
)
def test_abertura_recusada_com_outra_aberta_ou_sem_candidaturas(pedidos, codigo):
    """RN-15 e RN-16: só uma eleição aberta por vez, e só abre quem tem ao menos uma candidatura."""
    for pedido in pedidos:
        assert codigo_do_erro(abrir, **pedido) == codigo, pedido


def test_segundo_turno_so_abre_com_dois_candidatos_por_cargo():
    """RN-17 e RN-45: no 2º turno, cada cargo tem exatamente 2 candidaturas, e Senador não entra."""
    segundo_turno = uma_eleicao(turno=2)

    for quantidade in (1, 3):
        candidaturas = {Cargo.PRESIDENTE: 2, Cargo.GOVERNADOR: quantidade}
        recebido = codigo_do_erro(abrir, segundo_turno, candidaturas=candidaturas)
        assert recebido == "SEGUNDO_TURNO_INCOMPLETO", quantidade

    # Segunda barreira da RN-45: mesmo com 2 por cargo, o Senador não abre no 2º turno.
    com_senador = {Cargo.SENADOR: 2, Cargo.PRESIDENTE: 2}
    assert codigo_do_erro(abrir, segundo_turno, candidaturas=com_senador) == (
        "CARGO_NAO_PERMITIDO_NO_TURNO"
    )


# --- candidatura --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("aceitas", "recusadas"),
    [
        pytest.param(
            [(1, Cargo.SENADOR, "101", 0), (1, Cargo.PRESIDENTE, "50", 4)],  # o 1º turno é livre
            [(2, Cargo.SENADOR, "101", 0, "CARGO_NAO_PERMITIDO_NO_TURNO")],
            id="senador",
        ),
        pytest.param(
            [(2, Cargo.PRESIDENTE, "20", 1)],  # a segunda candidatura do cargo ainda passa
            [(2, Cargo.PRESIDENTE, "30", 2, "LIMITE_SEGUNDO_TURNO")],
            id="terceira-no-cargo",
        ),
    ],
)
def test_candidatura_no_segundo_turno_so_para_governador_e_presidente(aceitas, recusadas):
    """RN-45: no 2º turno só há Governador e Presidente, com no máximo 2 candidaturas por cargo."""
    for turno, cargo, numero, quantidade in aceitas:
        validar_candidatura(uma_eleicao(turno=turno), cargo, numero, quantidade)
    for turno, cargo, numero, quantidade, codigo in recusadas:
        eleicao = uma_eleicao(turno=turno)

        assert codigo_do_erro(validar_candidatura, eleicao, cargo, numero, quantidade) == codigo


def test_trocar_para_segundo_turno_confere_as_candidaturas_existentes():
    """RN-45: o 2º turno não herda Senador nem 3 candidaturas num cargo (409, com os cargos)."""
    validar_candidaturas_no_turno(1, {Cargo.SENADOR: 1, Cargo.PRESIDENTE: 3})  # o 1º turno é livre
    validar_candidaturas_no_turno(2, {Cargo.PRESIDENTE: 2, Cargo.GOVERNADOR: 1})  # cabem

    com_senador = erro_de(validar_candidaturas_no_turno, 2, {Cargo.SENADOR: 2, Cargo.PRESIDENTE: 2})
    com_tres = erro_de(validar_candidaturas_no_turno, 2, {Cargo.PRESIDENTE: 3, Cargo.GOVERNADOR: 1})

    assert com_senador.codigo == "CARGO_NAO_PERMITIDO_NO_TURNO"
    assert com_senador.detalhes == {"cargos": ["SENADOR"]}
    assert com_tres.codigo == "LIMITE_SEGUNDO_TURNO"
    assert com_tres.detalhes == {"cargos": ["PRESIDENTE"]}


# --- o que o service pede ao repository e quando faz commit --------------------------------


def test_abrir_eleicao_grava_o_status_e_o_horario_e_faz_commit():
    """RN-13 e RN-15: abrir deixa a eleição ABERTA, grava `aberta_em` e o retrato, e faz commit."""
    service = um_service()
    eleicao = uma_eleicao_gravada()
    candidatura = Candidatura(
        id=1,
        eleicao_id=7,
        candidato_id=3,
        partido_id=1,
        cargo=Cargo.PRESIDENTE.value,
        numero="13",
        criado_em=AGORA,
    )
    service.repository.obter_com_trava_exclusiva.return_value = eleicao
    service.repository.existe_eleicao_aberta.return_value = False
    service.repository.contar_candidaturas_por_cargo.return_value = UMA_CANDIDATURA
    service.repository.listar_candidaturas.return_value = [candidatura]
    service.candidatos.obter_resumos_de_candidatos.return_value = {
        3: CandidatoResumo(id=3, usuario_id=9, nome_urna="Ana", data_nascimento=date(1970, 1, 1))
    }

    aberta = service.abrir_eleicao(7, AGORA)

    assert (eleicao.status, eleicao.aberta_em) == ("ABERTA", AGORA)
    assert (aberta.status, aberta.aberta_em) == (StatusEleicao.ABERTA, AGORA)
    assert (candidatura.nome_urna, candidatura.data_nascimento) == ("Ana", date(1970, 1, 1))
    service.sessao.commit.assert_called_once_with()


def test_candidatura_com_a_eleicao_fora_de_agendada_responde_409():
    """RN-40: criar candidatura só com a eleição AGENDADA; senão 409, sem inserir nem commit."""
    service = um_service()
    service.repository.obter_com_trava_exclusiva.return_value = uma_eleicao_gravada(
        status=StatusEleicao.ABERTA.value, aberta_em=AGORA
    )
    dados = NovaCandidaturaDados(candidato_id=3, partido_id=1, cargo=Cargo.PRESIDENTE, numero="13")

    erro = erro_de(service.criar_candidatura, 7, dados, AGORA)

    assert erro.codigo == "ELEICAO_NAO_EDITAVEL"
    assert erro.detalhes == {"status": "ABERTA"}
    service.repository.inserir_candidatura.assert_not_called()
    service.sessao.commit.assert_not_called()


def um_erro_de_integridade(restricao: str | None) -> IntegrityError:
    """Um `IntegrityError` como o do PostgreSQL: o nome da restrição vem em `orig.diag`."""
    original = Exception("violação")
    original.diag = SimpleNamespace(constraint_name=restricao)
    return IntegrityError("INSERT ...", {}, original)


def test_candidatura_traduz_so_a_fk_do_candidato():
    """RN-46: candidato excluído entre a conferência e a gravação dá 422; outra violação sobe."""
    service = um_service()
    service.repository.obter_com_trava_exclusiva.return_value = uma_eleicao_gravada()
    service.repository.contar_candidaturas_no_cargo.return_value = 0
    service.repository.existe_numero_no_cargo.return_value = False
    service.repository.existe_candidatura_do_candidato.return_value = False
    dados = NovaCandidaturaDados(candidato_id=3, partido_id=1, cargo=Cargo.PRESIDENTE, numero="13")

    service.repository.inserir_candidatura.side_effect = um_erro_de_integridade(
        FK_CANDIDATO_DA_CANDIDATURA
    )
    erro = erro_de(service.criar_candidatura, 7, dados, AGORA)
    assert (erro.codigo, erro.detalhes) == ("REFERENCIA_INEXISTENTE", {"campo": "candidato_id"})

    service.repository.inserir_candidatura.side_effect = um_erro_de_integridade("ck_outra_regra")
    with pytest.raises(IntegrityError):
        service.criar_candidatura(7, dados, AGORA)

    assert service.sessao.rollback.call_count == 2
    service.sessao.commit.assert_not_called()
