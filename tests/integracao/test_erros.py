"""Formato de resposta de cada tratador de erro (seção 5 do PLANO).

As rotas abaixo existem só dentro deste teste, num app próprio. O app real não ganha rotas de teste.
"""

import logging
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import APIRouter, FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError

from app.compartilhado.erros import (
    AcessoNegado,
    ConflitoDeEstado,
    DadosInvalidos,
    NaoAutenticado,
    NaoEncontrado,
    registrar_tratadores,
    registro,
)
from app.compartilhado.validadores import cpf_valido, normalizar_cpf

ERROS_POR_TIPO = {
    "nao-autenticado": NaoAutenticado,
    "acesso-negado": AcessoNegado,
    "nao-encontrado": NaoEncontrado,
    "conflito": ConflitoDeEstado,
    "dados-invalidos": DadosInvalidos,
}


class ErroDoDriver(Exception):
    """Imita a exceção do psycopg: o PostgreSQL informa o nome da restrição em `diag`."""

    def __init__(self, restricao: str):
        super().__init__("violação de restrição")
        self.diag = SimpleNamespace(constraint_name=restricao)


class NovoUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpf: str
    idade: int

    @field_validator("cpf")
    @classmethod
    def conferir_cpf(cls, valor: str) -> str:
        if not cpf_valido(normalizar_cpf(valor)):
            raise ValueError("CPF inválido.")
        return valor


def criar_app_de_teste() -> FastAPI:
    """App só com os tratadores e as rotas que provocam cada tipo de erro."""
    roteador = APIRouter()

    @roteador.get("/erros/{tipo}")
    def levantar_erro_de_negocio(tipo: str):
        raise ERROS_POR_TIPO[tipo]("Mensagem do erro.", codigo="CODIGO_DO_TESTE")

    @roteador.get("/erro-com-detalhes")
    def levantar_erro_com_detalhes():
        raise ConflitoDeEstado(
            "A eleição não está aberta.",
            codigo="ELEICAO_NAO_ABERTA",
            detalhes={"status": "AGENDADA"},
        )

    @roteador.post("/validacao")
    def validar_corpo(entrada: NovoUsuario) -> dict:
        return {}

    @roteador.get("/consulta")
    def validar_consulta(pagina: Annotated[int, Query(ge=1)] = 1) -> dict:
        return {"pagina": pagina}

    @roteador.get("/integridade/{restricao}")
    def violar_restricao(restricao: str):
        raise IntegrityError("INSERT ...", {}, ErroDoDriver(restricao))

    @roteador.get("/integridade-sem-nome")
    def violar_restricao_sem_nome():
        raise IntegrityError("INSERT ...", {}, Exception("erro sem diagnóstico"))

    @roteador.get("/falha")
    def falhar():
        raise RuntimeError("senha do banco: segredo123")

    app = FastAPI()
    registrar_tratadores(app)
    app.include_router(roteador)
    return app


@pytest.fixture
def cliente_de_erros():
    # raise_server_exceptions=False: sem isso o TestClient relança a exceção no teste
    # em vez de entregar a resposta 500 que a aplicação de fato enviaria.
    return TestClient(criar_app_de_teste(), raise_server_exceptions=False)


def test_erro_de_negocio_responde_409_no_formato_padrao(cliente_de_erros):
    """Seção 5: ErroDeNegocio vira o status da classe e o corpo {"erro": {...}}."""
    resposta = cliente_de_erros.get("/erro-com-detalhes")

    assert resposta.status_code == 409
    assert resposta.json() == {
        "erro": {
            "codigo": "ELEICAO_NAO_ABERTA",
            "mensagem": "A eleição não está aberta.",
            "detalhes": {"status": "AGENDADA"},
        }
    }


@pytest.mark.parametrize(
    ("tipo", "status"),
    [
        ("nao-autenticado", 401),
        ("acesso-negado", 403),
        ("nao-encontrado", 404),
        ("conflito", 409),
        ("dados-invalidos", 422),
    ],
)
def test_cada_erro_de_negocio_usa_o_status_da_sua_classe(cliente_de_erros, tipo, status):
    """Seção 5: 401, 403, 404, 409 e 422 saem das subclasses, com detalhes vazios por padrão."""
    resposta = cliente_de_erros.get(f"/erros/{tipo}")

    assert resposta.status_code == status
    assert resposta.json() == {
        "erro": {"codigo": "CODIGO_DO_TESTE", "mensagem": "Mensagem do erro.", "detalhes": {}}
    }


def test_nao_autenticado_envia_o_cabecalho_www_authenticate(cliente_de_erros):
    """RN-06: o 401 diz ao cliente que o esquema de autenticação é Bearer."""
    resposta = cliente_de_erros.get("/erros/nao-autenticado")

    assert resposta.status_code == 401
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("tipo", ["acesso-negado", "nao-encontrado", "conflito", "dados-invalidos"])
def test_somente_o_401_envia_o_cabecalho_www_authenticate(cliente_de_erros, tipo):
    """RN-06: os outros erros de negócio não levam o cabeçalho de autenticação."""
    resposta = cliente_de_erros.get(f"/erros/{tipo}")

    assert "WWW-Authenticate" not in resposta.headers


def test_cpf_invalido_no_corpo_responde_422_com_o_campo_e_a_mensagem(cliente_de_erros):
    """Seção 10: o 422 lista os campos com problema; o prefixo 'Value error' do Pydantic sai."""
    resposta = cliente_de_erros.post("/validacao", json={"cpf": "123", "idade": 20})

    assert resposta.status_code == 422
    assert resposta.json() == {
        "erro": {
            "codigo": "DADOS_INVALIDOS",
            "mensagem": "Dados inválidos na requisição.",
            "detalhes": {"campos": [{"campo": "cpf", "mensagem": "CPF inválido."}]},
        }
    }


def test_validacao_lista_todos_os_campos_com_problema(cliente_de_erros):
    """Seção 10: campo faltando, tipo errado e campo extra aparecem juntos, sem o prefixo 'body'."""
    resposta = cliente_de_erros.post("/validacao", json={"idade": "abc", "perfil": "CHEFE_SECAO"})

    campos = resposta.json()["erro"]["detalhes"]["campos"]
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert {item["campo"] for item in campos} == {"cpf", "idade", "perfil"}
    assert all(item["mensagem"] for item in campos)


def test_validacao_de_parametro_da_consulta_nao_leva_o_prefixo_query(cliente_de_erros):
    """Seção 10: o nome do campo é o do parâmetro ('pagina'), sem dizer de onde ele veio."""
    resposta = cliente_de_erros.get("/consulta", params={"pagina": 0})

    campos = resposta.json()["erro"]["detalhes"]["campos"]
    assert resposta.status_code == 422
    assert [item["campo"] for item in campos] == ["pagina"]


@pytest.mark.parametrize(
    ("restricao", "codigo"),
    [
        ("uq_usuarios_cpf", "CPF_JA_CADASTRADO"),
        ("uq_eleitores_titulo_eleitor", "TITULO_JA_CADASTRADO"),
        ("uq_partidos_sigla", "PARTIDO_DUPLICADO"),
        ("uq_partidos_numero", "PARTIDO_DUPLICADO"),
        ("uq_partidos_nome", "PARTIDO_DUPLICADO"),
        ("uq_eleicoes_data_turno", "ELEICAO_DUPLICADA"),
        ("uq_eleicoes_uma_aberta", "OUTRA_ELEICAO_ABERTA"),
        ("uq_candidaturas_eleicao_id_cargo_numero", "NUMERO_JA_UTILIZADO"),
        ("uq_candidaturas_eleicao_id_candidato_id", "CANDIDATURA_DUPLICADA"),
        ("pk_registros_votacao", "VOTO_JA_REGISTRADO"),
        ("fk_registros_votacao_eleitor_id_eleitores", "EXCLUSAO_BLOQUEADA"),
        ("fk_candidaturas_candidato_id_candidatos", "EXCLUSAO_BLOQUEADA"),
    ],
)
def test_integridade_e_traduzida_pelo_nome_da_restricao(cliente_de_erros, restricao, codigo):
    """Seção 6: cada restrição do banco vira um 409 com o código da tabela de tradução."""
    resposta = cliente_de_erros.get(f"/integridade/{restricao}")

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == codigo
    assert resposta.json()["erro"]["detalhes"] == {}


def test_integridade_de_restricao_desconhecida_vira_conflito_de_dados(cliente_de_erros):
    """Seção 5: restrição que não está na tabela cai no código genérico CONFLITO_DE_DADOS."""
    resposta = cliente_de_erros.get("/integridade/uq_restricao_que_nao_existe")

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "CONFLITO_DE_DADOS"


def test_integridade_sem_nome_de_restricao_vira_conflito_de_dados(cliente_de_erros):
    """Seção 5: se o driver não informa a restrição, o código também é CONFLITO_DE_DADOS."""
    resposta = cliente_de_erros.get("/integridade-sem-nome")

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "CONFLITO_DE_DADOS"


def test_excecao_inesperada_responde_500_sem_vazar_a_mensagem_original(
    cliente_de_erros, caplog, monkeypatch
):
    """Proteção 'Erros sem vazamento': a resposta é genérica e o detalhe fica só no log."""
    # O migrations/env.py chama logging.config.fileConfig (fixture banco_migrado), que desliga
    # os loggers já criados. Só o teste religa o logger; o app real nunca chama fileConfig.
    monkeypatch.setattr(registro, "disabled", False)

    with caplog.at_level(logging.ERROR):
        resposta = cliente_de_erros.get("/falha")

    assert resposta.status_code == 500
    assert resposta.json() == {
        "erro": {
            "codigo": "ERRO_INTERNO",
            "mensagem": "Erro interno. Tente novamente mais tarde.",
            "detalhes": {},
        }
    }
    assert "segredo123" not in resposta.text
    assert "RuntimeError" not in resposta.text
    assert "segredo123" in caplog.text
