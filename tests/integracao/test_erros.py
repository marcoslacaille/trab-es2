"""Formato de resposta de cada tratador de erro.

As rotas abaixo existem só dentro deste teste, num app próprio. O app real não ganha rotas de teste.
"""

import logging
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    AcessoNegado,
    ConflitoDeEstado,
    DadosInvalidos,
    NaoAutenticado,
    NaoEncontrado,
)
from app.core.validadores import cpf_valido, normalizar_cpf
from app.core.web import registrar_tratadores, registro

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

    @roteador.get("/status-http/{codigo}")
    def levantar_erro_http(codigo: int):
        raise HTTPException(status_code=codigo, detail="texto do framework em inglês")

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


def test_erro_de_negocio_usa_o_formato_padrao_e_o_status_da_classe(cliente_de_erros):
    """ErroDeNegocio vira o status da classe e o corpo {"erro": {...}}."""
    resposta = cliente_de_erros.get("/erro-com-detalhes")

    assert resposta.status_code == 409
    assert resposta.json() == {
        "erro": {
            "codigo": "ELEICAO_NAO_ABERTA",
            "mensagem": "A eleição não está aberta.",
            "detalhes": {"status": "AGENDADA"},
        }
    }

    # 401, 403, 404, 409 e 422 saem das subclasses, com detalhes vazios por padrão.
    status_por_tipo = {
        "nao-autenticado": 401,
        "acesso-negado": 403,
        "nao-encontrado": 404,
        "conflito": 409,
        "dados-invalidos": 422,
    }
    for tipo, status in status_por_tipo.items():
        resposta = cliente_de_erros.get(f"/erros/{tipo}")

        assert resposta.status_code == status, tipo
        assert resposta.json() == {
            "erro": {"codigo": "CODIGO_DO_TESTE", "mensagem": "Mensagem do erro.", "detalhes": {}}
        }


def test_so_o_401_envia_o_cabecalho_www_authenticate(cliente_de_erros):
    """RN-06: o 401 diz que o esquema é Bearer; os outros erros de negócio não têm o cabeçalho."""
    nao_autenticado = cliente_de_erros.get("/erros/nao-autenticado")

    assert nao_autenticado.status_code == 401
    assert nao_autenticado.headers["WWW-Authenticate"] == "Bearer"
    for tipo in ("acesso-negado", "nao-encontrado", "conflito", "dados-invalidos"):
        resposta = cliente_de_erros.get(f"/erros/{tipo}")

        assert "WWW-Authenticate" not in resposta.headers, tipo


def test_validacao_lista_os_campos_com_problema(cliente_de_erros):
    """O 422 lista os campos com problema, sem o prefixo 'Value error', 'body' nem 'query'."""
    resposta = cliente_de_erros.post("/validacao", json={"cpf": "123", "idade": 20})

    assert resposta.status_code == 422
    assert resposta.json() == {
        "erro": {
            "codigo": "DADOS_INVALIDOS",
            "mensagem": "Dados inválidos na requisição.",
            "detalhes": {"campos": [{"campo": "cpf", "mensagem": "CPF inválido."}]},
        }
    }

    # Campo faltando, tipo errado e campo extra aparecem juntos.
    varios = cliente_de_erros.post("/validacao", json={"idade": "abc", "perfil": "CHEFE_SECAO"})
    campos = varios.json()["erro"]["detalhes"]["campos"]
    assert varios.status_code == 422
    assert varios.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert {item["campo"] for item in campos} == {"cpf", "idade", "perfil"}
    assert all(item["mensagem"] for item in campos)

    # O parâmetro de consulta tem o nome do parâmetro ('pagina'), sem dizer de onde veio.
    consulta = cliente_de_erros.get("/consulta", params={"pagina": 0})
    assert consulta.status_code == 422
    assert [item["campo"] for item in consulta.json()["erro"]["detalhes"]["campos"]] == ["pagina"]


def test_integridade_e_traduzida_pelo_nome_da_restricao(cliente_de_erros):
    """Cada restrição do banco vira um 409 com o código da tabela de tradução."""
    traducao = [
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
        # Restrição que não está na tabela, e erro do driver sem o nome da restrição.
        ("uq_restricao_que_nao_existe", "CONFLITO_DE_DADOS"),
    ]

    for restricao, codigo in traducao:
        resposta = cliente_de_erros.get(f"/integridade/{restricao}")

        assert resposta.status_code == 409, restricao
        assert resposta.json()["erro"]["codigo"] == codigo, restricao
        assert resposta.json()["erro"]["detalhes"] == {}, restricao

    sem_nome = cliente_de_erros.get("/integridade-sem-nome")
    assert sem_nome.status_code == 409
    assert sem_nome.json()["erro"]["codigo"] == "CONFLITO_DE_DADOS"


def test_excecao_inesperada_responde_500_sem_vazar_a_mensagem(
    cliente_de_erros, caplog, monkeypatch
):
    """Erros sem vazamento: a resposta é genérica e o detalhe fica só no log."""
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


def test_erros_do_framework_usam_o_formato_padrao(cliente, cliente_de_erros):
    """O 404, o 405 e os outros erros do framework também usam {"erro": {...}}."""
    nao_encontrada = cliente.get("/rota-que-nao-existe")

    assert nao_encontrada.status_code == 404
    assert nao_encontrada.json() == {
        "erro": {
            "codigo": "ROTA_NAO_ENCONTRADA",
            "mensagem": "Rota não encontrada.",
            "detalhes": {},
        }
    }

    nao_permitido = cliente.delete("/health")
    assert nao_permitido.status_code == 405
    assert nao_permitido.json() == {
        "erro": {
            "codigo": "METODO_NAO_PERMITIDO",
            "mensagem": "Método não permitido para esta rota.",
            "detalhes": {},
        }
    }
    assert "GET" in nao_permitido.headers["Allow"]

    # Qualquer outro status do framework vira ERRO_HTTP, sem repassar o texto.
    outro = cliente_de_erros.get("/status-http/400")
    assert outro.status_code == 400
    assert outro.json() == {
        "erro": {"codigo": "ERRO_HTTP", "mensagem": "Erro na requisição.", "detalhes": {}}
    }
