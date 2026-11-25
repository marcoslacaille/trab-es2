from datetime import datetime

from app.core.database import SessionLocal
from app.core.relogio import agora
from app.models.enums import Perfil
from app.services.usuario_service import UsuarioService
from tests.auxiliares import (
    SENHA_ELEITOR,
    eleicao_aberta_com_candidatos,
    gerar_cpf,
    login,
    novo_eleitor,
    votar,
)

ROTA = "/api/v1/eleitores"


def _entrar(cliente, cpf, senha):
    return cliente.post("/api/v1/auth/login", data={"username": cpf, "password": senha})


def _com_pontuacao(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _criar_candidato(cpf: str) -> None:
    """Cria uma credencial de candidato direto pelo serviço (o módulo de candidatos é posterior)."""
    with SessionLocal() as sessao:
        UsuarioService(sessao).criar_credencial(
            cpf, "Candidato de Teste", "Candidato@123", Perfil.CANDIDATO, agora()
        )
        sessao.commit()


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def test_cadastrar_eleitor_devolve_201_sem_senha_e_ele_consegue_entrar(
    cliente, cabecalho_chefe, relogio
):
    """RN-20 e RN-07: cadastra com CPF pontuado, não devolve senha e o login funciona."""
    cpf = gerar_cpf(5)

    resposta = novo_eleitor(cliente, cabecalho_chefe, cpf=_com_pontuacao(cpf), nome="Ana Souza")

    corpo = resposta.json()
    assert resposta.status_code == 201
    assert corpo["nome"] == "Ana Souza"
    assert corpo["cpf"] == cpf
    assert "senha" not in corpo
    assert "senha_hash" not in corpo
    assert datetime.fromisoformat(corpo["criado_em"]) == relogio.atual
    assert _entrar(cliente, cpf, SENHA_ELEITOR).status_code == 200


def test_cadastrar_eleitor_recusa_dados_invalidos(cliente, cabecalho_chefe):
    """RN-07, RN-21, RN-22 e RN-23: cada dado fora da regra dá 422 e não cria a credencial."""
    cpf_do_menor = gerar_cpf(902)
    casos = [
        ({"cpf": "111.111.111-11"}, "CPF_INVALIDO"),
        ({"titulo_eleitor": "12345678901"}, "DADOS_INVALIDOS"),
        ({"titulo_eleitor": "12345678901a"}, "DADOS_INVALIDOS"),
        # Um dia antes dos 16 anos completos na data do cadastro (25/11/2026).
        ({"cpf": cpf_do_menor, "data_nascimento": "2010-11-26"}, "IDADE_MINIMA"),
        ({"perfil": "CHEFE_SECAO"}, "DADOS_INVALIDOS"),
    ]

    for sobrescritas, codigo in casos:
        resposta = novo_eleitor(cliente, cabecalho_chefe, **sobrescritas)

        assert resposta.status_code == 422, sobrescritas
        assert _codigo(resposta) == codigo, sobrescritas

    assert _entrar(cliente, cpf_do_menor, SENHA_ELEITOR).status_code == 401


def test_cpf_e_unico_entre_eleitores_e_candidatos(cliente, cabecalho_chefe):
    """RN-07 e RN-21: CPF repetido (de eleitor ou de candidato) e título repetido dão 409."""
    primeiro = novo_eleitor(cliente, cabecalho_chefe).json()
    cpf_de_candidato = gerar_cpf(900)
    _criar_candidato(cpf_de_candidato)

    de_outro_eleitor = novo_eleitor(cliente, cabecalho_chefe, cpf=primeiro["cpf"])
    de_um_candidato = novo_eleitor(cliente, cabecalho_chefe, cpf=cpf_de_candidato)

    for resposta in (de_outro_eleitor, de_um_candidato):
        assert resposta.status_code == 409
        assert _codigo(resposta) == "CPF_JA_CADASTRADO"

    cpf_novo = gerar_cpf(901)
    titulo = novo_eleitor(
        cliente, cabecalho_chefe, cpf=cpf_novo, titulo_eleitor=primeiro["titulo_eleitor"]
    )
    assert titulo.status_code == 409
    assert _codigo(titulo) == "TITULO_JA_CADASTRADO"
    assert _entrar(cliente, cpf_novo, SENHA_ELEITOR).status_code == 401


def test_alterar_eleitor_muda_nome_e_senha_mas_nao_cpf_nem_titulo(cliente, cabecalho_chefe):
    """RN-22 e RN-23: altera nome, senha e nascimento; CPF e título não mudam (422)."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()
    rota = f"{ROTA}/{eleitor['id']}"

    resposta = cliente.patch(
        rota,
        json={"nome": "Nome Novo da Silva", "senha": "NovaSenha@456"},
        headers=cabecalho_chefe,
    )

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Nome Novo da Silva"
    assert resposta.json()["cpf"] == eleitor["cpf"]
    assert _entrar(cliente, eleitor["cpf"], SENHA_ELEITOR).status_code == 401
    assert _entrar(cliente, eleitor["cpf"], "NovaSenha@456").status_code == 200

    # A nova data de nascimento também precisa de 16 anos completos.
    valida = cliente.patch(rota, json={"data_nascimento": "2000-01-31"}, headers=cabecalho_chefe)
    menor = cliente.patch(rota, json={"data_nascimento": "2015-01-01"}, headers=cabecalho_chefe)
    assert valida.status_code == 200
    assert valida.json()["data_nascimento"] == "2000-01-31"
    assert menor.status_code == 422
    assert _codigo(menor) == "IDADE_MINIMA"

    com_cpf = cliente.patch(rota, json={"cpf": gerar_cpf(903)}, headers=cabecalho_chefe)
    com_titulo = cliente.patch(
        rota, json={"titulo_eleitor": "999999999999"}, headers=cabecalho_chefe
    )
    for resposta in (com_cpf, com_titulo):
        assert resposta.status_code == 422
        assert _codigo(resposta) == "DADOS_INVALIDOS"


def test_excluir_eleitor_que_nao_votou_apaga_tambem_a_credencial(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-24: exclui com 204 e o login falha; quem já votou não se exclui (409)."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()

    resposta = cliente.delete(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe)

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert _entrar(cliente, eleitor["cpf"], SENHA_ELEITOR).status_code == 401
    consulta = cliente.get(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe)
    assert consulta.status_code == 404
    assert _codigo(consulta) == "ELEITOR_NAO_ENCONTRADO"

    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201
    votante = cliente.get(f"{ROTA}/eu", headers=cabecalho_eleitor).json()

    bloqueada = cliente.delete(f"{ROTA}/{votante['id']}", headers=cabecalho_chefe)

    assert bloqueada.status_code == 409
    assert _codigo(bloqueada) == "EXCLUSAO_BLOQUEADA"
    assert cliente.get(f"{ROTA}/{votante['id']}", headers=cabecalho_chefe).status_code == 200


def test_listar_eleitores_filtra_por_nome_e_pagina_sem_mostrar_a_senha(cliente, cabecalho_chefe):
    """RN-20 e RN-25: filtro, ordem, paginação, sem senha; `/eleitores/eu` devolve o logado."""
    criados = {}
    for nome in ("Ana Souza", "Bruno Lima", "Ana Paula Dias"):
        resposta = novo_eleitor(cliente, cabecalho_chefe, nome=nome)
        assert resposta.status_code == 201
        criados[nome] = resposta.json()

    filtrada = cliente.get(ROTA, params={"nome": "ANA"}, headers=cabecalho_chefe).json()
    segunda = cliente.get(ROTA, params={"pagina": 2, "tamanho": 1}, headers=cabecalho_chefe).json()

    assert [e["nome"] for e in filtrada["itens"]] == ["Ana Paula Dias", "Ana Souza"]
    assert filtrada["total"] == 2
    assert [e["nome"] for e in segunda["itens"]] == ["Ana Souza"]
    assert (segunda["pagina"], segunda["tamanho"], segunda["total"]) == (2, 1, 3)
    todos = cliente.get(ROTA, headers=cabecalho_chefe).json()
    assert todos["total"] == 3  # o Chefe não aparece na lista de eleitores
    assert all("senha" not in item for item in todos["itens"])

    inexistente = cliente.get(f"{ROTA}/999", headers=cabecalho_chefe)
    assert inexistente.status_code == 404
    assert _codigo(inexistente) == "ELEITOR_NAO_ENCONTRADO"

    meu = criados["Bruno Lima"]
    cabecalho = login(cliente, meu["cpf"], SENHA_ELEITOR)
    resposta = cliente.get(f"{ROTA}/eu", headers=cabecalho)
    corpo = resposta.json()
    assert resposta.status_code == 200
    assert corpo["id"] == meu["id"]
    assert corpo["nome"] == "Bruno Lima"
    assert corpo["cpf"] == meu["cpf"]
    assert corpo["titulo_eleitor"] == meu["titulo_eleitor"]
    # O banco devolve o horário em outro fuso; o instante é o mesmo.
    assert datetime.fromisoformat(corpo["criado_em"]) == datetime.fromisoformat(meu["criado_em"])
