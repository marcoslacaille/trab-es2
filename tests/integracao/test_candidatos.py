from datetime import datetime

from tests.auxiliares import (
    SENHA_CANDIDATO,
    gerar_cpf,
    nova_candidatura,
    nova_eleicao,
    novo_candidato,
)

ROTA_CANDIDATOS = "/api/v1/candidatos"


def _entrar(cliente, cpf, senha):
    return cliente.post("/api/v1/auth/login", data={"username": cpf, "password": senha})


def _com_pontuacao(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _mesmos_dados(a: dict, b: dict) -> bool:
    """Compara duas respostas de candidato; `criado_em` vale pelo instante, não pelo texto."""
    outros_campos_iguais = {k: v for k, v in a.items() if k != "criado_em"} == {
        k: v for k, v in b.items() if k != "criado_em"
    }
    return outros_campos_iguais and (
        datetime.fromisoformat(a["criado_em"]) == datetime.fromisoformat(b["criado_em"])
    )


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def test_cadastrar_candidato_devolve_201_sem_senha_e_ele_consegue_entrar(
    cliente, cabecalho_chefe, relogio
):
    """RN-30, RN-31 e RN-07: cadastra com CPF pontuado, sem senha na resposta, e ele se consulta."""
    cpf = gerar_cpf(7001)

    resposta = novo_candidato(
        cliente,
        cabecalho_chefe,
        cpf=_com_pontuacao(cpf),
        nome="Carlos Henrique Lima",
        nome_urna="  Carlos Lima  ",
    )

    corpo = resposta.json()
    assert resposta.status_code == 201
    assert corpo["nome"] == "Carlos Henrique Lima"
    assert corpo["nome_urna"] == "Carlos Lima"
    assert corpo["cpf"] == cpf
    assert corpo["data_nascimento"] == "1968-03-05"
    assert "senha" not in corpo
    assert "senha_hash" not in corpo
    assert datetime.fromisoformat(corpo["criado_em"]) == relogio.atual
    entrada = _entrar(cliente, cpf, SENHA_CANDIDATO)
    assert entrada.status_code == 200
    cabecalho = {"Authorization": f"Bearer {entrada.json()['access_token']}"}
    eu = cliente.get(f"{ROTA_CANDIDATOS}/eu", headers=cabecalho)
    assert eu.status_code == 200
    assert _mesmos_dados(eu.json(), corpo)


def test_cadastrar_candidato_recusa_dados_invalidos(cliente, cabecalho_chefe):
    """RN-03, RN-05, RN-07 e RN-31: cada dado fora da regra dá 422 e não cria a credencial."""
    cpf_do_nascimento_de_hoje = gerar_cpf(7002)
    casos = [
        ({"nome_urna": "Jo"}, "DADOS_INVALIDOS"),
        ({"nome_urna": "x" * 31}, "DADOS_INVALIDOS"),
        ({"cpf": cpf_do_nascimento_de_hoje, "data_nascimento": "2026-11-25"}, "DADOS_INVALIDOS"),
        ({"data_nascimento": "2030-01-01"}, "DADOS_INVALIDOS"),
        ({"cpf": "111.111.111-11"}, "CPF_INVALIDO"),
        ({"senha": "123"}, "SENHA_INVALIDA"),
        ({"perfil": "CHEFE_SECAO"}, "DADOS_INVALIDOS"),
    ]

    for sobrescritas, codigo in casos:
        resposta = novo_candidato(cliente, cabecalho_chefe, **sobrescritas)

        assert resposta.status_code == 422, sobrescritas
        assert _codigo(resposta) == codigo, sobrescritas

    assert _entrar(cliente, cpf_do_nascimento_de_hoje, SENHA_CANDIDATO).status_code == 401
    limite = novo_candidato(cliente, cabecalho_chefe, nome_urna="x" * 30)
    assert limite.status_code == 201


def test_listar_candidatos_filtra_por_nome_e_pagina(cliente, cabecalho_chefe):
    """RN-30: o Chefe lista candidatos por nome, com paginação, e consulta um por id."""
    novo_candidato(cliente, cabecalho_chefe, nome="Ana Paula Reis")
    novo_candidato(cliente, cabecalho_chefe, nome="Bruno Teixeira")
    novo_candidato(cliente, cabecalho_chefe, nome="Ana Clara Dias")

    todos = cliente.get(ROTA_CANDIDATOS, params={"tamanho": 2}, headers=cabecalho_chefe).json()
    so_ana = cliente.get(ROTA_CANDIDATOS, params={"nome": "ana"}, headers=cabecalho_chefe).json()

    assert todos["total"] == 3
    assert [c["nome"] for c in todos["itens"]] == ["Ana Clara Dias", "Ana Paula Reis"]
    assert [c["nome"] for c in so_ana["itens"]] == ["Ana Clara Dias", "Ana Paula Reis"]

    encontrado = cliente.get(
        f"{ROTA_CANDIDATOS}/{todos['itens'][0]['id']}", headers=cabecalho_chefe
    )
    inexistente = cliente.get(f"{ROTA_CANDIDATOS}/9999", headers=cabecalho_chefe)
    assert encontrado.status_code == 200
    assert _mesmos_dados(encontrado.json(), todos["itens"][0])
    assert inexistente.status_code == 404
    assert _codigo(inexistente) == "CANDIDATO_NAO_ENCONTRADO"


def test_alterar_candidato_muda_nome_de_urna_e_senha_mas_nao_o_cpf(cliente, cabecalho_chefe):
    """RN-31 e RN-33: troca nome de urna e senha; CPF, dado inválido e id inexistente falham."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()
    rota = f"{ROTA_CANDIDATOS}/{criado['id']}"

    alterado = cliente.patch(
        rota, json={"nome_urna": "Novo Nome", "senha": "NovaSenha@456"}, headers=cabecalho_chefe
    )
    com_cpf = cliente.patch(rota, json={"cpf": gerar_cpf(7003)}, headers=cabecalho_chefe)

    assert alterado.status_code == 200
    assert alterado.json()["nome_urna"] == "Novo Nome"
    assert alterado.json()["cpf"] == criado["cpf"]
    assert _entrar(cliente, criado["cpf"], "NovaSenha@456").status_code == 200
    assert _entrar(cliente, criado["cpf"], SENHA_CANDIDATO).status_code == 401
    assert com_cpf.status_code == 422

    urna_curta = cliente.patch(rota, json={"nome_urna": "Jo"}, headers=cabecalho_chefe)
    nascimento = cliente.patch(
        rota, json={"data_nascimento": "2030-01-01"}, headers=cabecalho_chefe
    )
    inexistente = cliente.patch(
        f"{ROTA_CANDIDATOS}/9999", json={"nome_urna": "Algum"}, headers=cabecalho_chefe
    )
    assert urna_curta.status_code == 422
    assert nascimento.status_code == 422
    assert _codigo(nascimento) == "DADOS_INVALIDOS"
    assert inexistente.status_code == 404


def test_excluir_candidato_sem_candidaturas_remove_tambem_a_credencial(cliente, cabecalho_chefe):
    """RN-33: com candidatura → 409 `EXCLUSAO_BLOQUEADA`; sem ela → 204 e o login deixa de valer.

    Confirma que a FK `fk_candidaturas_candidato_id_candidatos` tem o nome que o serviço espera:
    se tivesse outro, o erro seria o genérico `CONFLITO_DE_DADOS`.
    """
    candidato = novo_candidato(cliente, cabecalho_chefe).json()
    nova_eleicao(cliente, cabecalho_chefe)
    candidatura = nova_candidatura(cliente, cabecalho_chefe, candidato_id=candidato["id"]).json()
    rota = f"{ROTA_CANDIDATOS}/{candidato['id']}"

    bloqueada = cliente.delete(rota, headers=cabecalho_chefe)

    assert bloqueada.status_code == 409
    assert _codigo(bloqueada) == "EXCLUSAO_BLOQUEADA"
    assert cliente.get(rota, headers=cabecalho_chefe).status_code == 200  # nada foi apagado

    remocao = cliente.delete(
        f"/api/v1/eleicoes/1/candidaturas/{candidatura['id']}", headers=cabecalho_chefe
    )
    liberada = cliente.delete(rota, headers=cabecalho_chefe)

    assert remocao.status_code == 204
    assert liberada.status_code == 204
    assert cliente.get(rota, headers=cabecalho_chefe).status_code == 404
    assert _entrar(cliente, candidato["cpf"], SENHA_CANDIDATO).status_code == 401
