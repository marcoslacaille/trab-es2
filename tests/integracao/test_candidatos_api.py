from datetime import datetime

from tests.auxiliares import (
    SENHA_CANDIDATO,
    gerar_cpf,
    nova_candidatura,
    nova_eleicao,
    novo_candidato,
    novo_partido,
)

ROTA_CANDIDATOS = "/api/v1/candidatos"
ROTA_PARTIDOS = "/api/v1/partidos"


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


# ---------------------------------------------------------------- partidos (TI-27)


def test_criar_partido_devolve_201_com_sigla_em_maiusculas(cliente, cabecalho_chefe):
    """TI-27 / RN-32: a sigla digitada em minúsculas é gravada em maiúsculas."""
    resposta = novo_partido(
        cliente, cabecalho_chefe, sigla="pino", nome="Partido da Inovação", numero=10
    )

    assert resposta.status_code == 201
    assert resposta.json() == {
        "id": 1,
        "sigla": "PINO",
        "nome": "Partido da Inovação",
        "numero": 10,
    }


def test_criar_partido_recusa_sigla_repetida(cliente, cabecalho_chefe):
    """TI-27 / RN-32: sigla já usada dá 409 PARTIDO_DUPLICADO (mesmo em outra caixa)."""
    novo_partido(cliente, cabecalho_chefe, sigla="PINO")

    resposta = novo_partido(cliente, cabecalho_chefe, sigla="pino")

    assert resposta.status_code == 409
    assert _codigo(resposta) == "PARTIDO_DUPLICADO"


def test_criar_partido_recusa_numero_repetido(cliente, cabecalho_chefe):
    """TI-27 / RN-32: número já usado dá 409 PARTIDO_DUPLICADO."""
    novo_partido(cliente, cabecalho_chefe, numero=13)

    resposta = novo_partido(cliente, cabecalho_chefe, numero=13)

    assert resposta.status_code == 409
    assert _codigo(resposta) == "PARTIDO_DUPLICADO"


def test_criar_partido_recusa_nome_repetido(cliente, cabecalho_chefe):
    """TI-27 / RN-32: nome já usado dá 409 PARTIDO_DUPLICADO."""
    novo_partido(cliente, cabecalho_chefe, nome="Partido Unico")

    resposta = novo_partido(cliente, cabecalho_chefe, nome="Partido Unico")

    assert resposta.status_code == 409
    assert _codigo(resposta) == "PARTIDO_DUPLICADO"


def test_criar_partido_recusa_dados_fora_do_formato(cliente, cabecalho_chefe):
    """TI-27 / RN-32: sigla curta ou com símbolo, número fora de 10 a 99 e nome vazio dão 422."""
    sigla_curta = novo_partido(cliente, cabecalho_chefe, sigla="A")
    sigla_com_simbolo = novo_partido(cliente, cabecalho_chefe, sigla="AB-C")
    numero_baixo = novo_partido(cliente, cabecalho_chefe, numero=9)
    numero_alto = novo_partido(cliente, cabecalho_chefe, numero=100)
    nome_vazio = novo_partido(cliente, cabecalho_chefe, nome="")

    for resposta in (sigla_curta, sigla_com_simbolo, numero_baixo, numero_alto, nome_vazio):
        assert resposta.status_code == 422
        assert _codigo(resposta) == "DADOS_INVALIDOS"


def test_criar_partido_exige_perfil_chefe(cliente, cabecalho_eleitor, cabecalho_candidato):
    """TI-27 / RN-30: eleitor e candidato não cadastram partidos."""
    do_eleitor = novo_partido(cliente, cabecalho_eleitor)
    do_candidato = novo_partido(cliente, cabecalho_candidato)

    assert do_eleitor.status_code == 403
    assert do_candidato.status_code == 403
    assert _codigo(do_eleitor) == "PERFIL_NAO_AUTORIZADO"


def test_listar_partidos_por_numero_para_qualquer_usuario_logado(
    cliente, cabecalho_chefe, cabecalho_eleitor, cabecalho_candidato
):
    """TI-27 / RN-30: eleitor, candidato e Chefe listam os partidos, ordenados por número."""
    novo_partido(cliente, cabecalho_chefe, sigla="BB", numero=30)
    novo_partido(cliente, cabecalho_chefe, sigla="AA", numero=20)

    for cabecalho in (cabecalho_eleitor, cabecalho_candidato, cabecalho_chefe):
        resposta = cliente.get(ROTA_PARTIDOS, headers=cabecalho)

        assert resposta.status_code == 200
        assert [partido["sigla"] for partido in resposta.json()] == ["AA", "BB"]


def test_listar_partidos_sem_token_da_401(cliente):
    """TI-27 / RN-30: sem login não se lista partido."""
    resposta = cliente.get(ROTA_PARTIDOS)

    assert resposta.status_code == 401
    assert _codigo(resposta) == "NAO_AUTENTICADO"


# ---------------------------------------------------------------- candidatos (TI-28)


def test_cadastrar_candidato_devolve_201_sem_senha_e_ele_consegue_entrar(
    cliente, cabecalho_chefe, relogio
):
    """TI-28 / RN-30, RN-31, RN-07: cadastra com CPF pontuado, sem senha na resposta."""
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
    assert _entrar(cliente, cpf, SENHA_CANDIDATO).status_code == 200


def test_candidato_consulta_os_proprios_dados_em_candidatos_eu(cliente, cabecalho_chefe):
    """TI-28 / RN-30: o candidato logado vê os próprios dados em /candidatos/eu."""
    cadastrado = novo_candidato(cliente, cabecalho_chefe, nome_urna="Marina Costa").json()
    cabecalho = {
        "Authorization": "Bearer "
        + _entrar(cliente, cadastrado["cpf"], SENHA_CANDIDATO).json()["access_token"]
    }

    resposta = cliente.get(f"{ROTA_CANDIDATOS}/eu", headers=cabecalho)

    assert resposta.status_code == 200
    assert _mesmos_dados(resposta.json(), cadastrado)


def test_candidatos_eu_nao_serve_para_chefe_nem_eleitor(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-28 / RN-30: /candidatos/eu é só do candidato; e sem token dá 401."""
    do_chefe = cliente.get(f"{ROTA_CANDIDATOS}/eu", headers=cabecalho_chefe)
    do_eleitor = cliente.get(f"{ROTA_CANDIDATOS}/eu", headers=cabecalho_eleitor)
    sem_token = cliente.get(f"{ROTA_CANDIDATOS}/eu")

    assert do_chefe.status_code == 403
    assert do_eleitor.status_code == 403
    assert _codigo(do_chefe) == "PERFIL_NAO_AUTORIZADO"
    assert sem_token.status_code == 401


def test_cadastrar_candidato_exige_perfil_chefe(cliente, cabecalho_eleitor, cabecalho_candidato):
    """TI-28 / RN-30: eleitor e candidato não cadastram candidatos."""
    do_eleitor = novo_candidato(cliente, cabecalho_eleitor)
    do_candidato = novo_candidato(cliente, cabecalho_candidato)

    assert do_eleitor.status_code == 403
    assert do_candidato.status_code == 403


def test_cadastrar_candidato_recusa_nome_de_urna_fora_de_3_a_30(cliente, cabecalho_chefe):
    """TI-28 / RN-31: nome de urna com 2 ou com 31 caracteres dá 422."""
    curto = novo_candidato(cliente, cabecalho_chefe, nome_urna="Jo")
    longo = novo_candidato(cliente, cabecalho_chefe, nome_urna="x" * 31)
    limite = novo_candidato(cliente, cabecalho_chefe, nome_urna="x" * 30)

    assert curto.status_code == 422
    assert longo.status_code == 422
    assert _codigo(curto) == "DADOS_INVALIDOS"
    assert limite.status_code == 201


def test_cadastrar_candidato_recusa_nascimento_que_nao_esta_no_passado(cliente, cabecalho_chefe):
    """TI-28 / RN-31: nascimento hoje (25/11/2026) ou no futuro dá 422 sem criar credencial."""
    cpf = gerar_cpf(7002)

    hoje = novo_candidato(cliente, cabecalho_chefe, cpf=cpf, data_nascimento="2026-11-25")
    futuro = novo_candidato(cliente, cabecalho_chefe, data_nascimento="2030-01-01")

    assert hoje.status_code == 422
    assert futuro.status_code == 422
    assert _codigo(hoje) == "DADOS_INVALIDOS"
    assert _entrar(cliente, cpf, SENHA_CANDIDATO).status_code == 401


def test_cadastrar_candidato_recusa_cpf_invalido_e_repetido(cliente, cabecalho_chefe):
    """TI-28 / RN-07: CPF inválido dá 422 CPF_INVALIDO; repetido dá 409 CPF_JA_CADASTRADO."""
    invalido = novo_candidato(cliente, cabecalho_chefe, cpf="111.111.111-11")
    primeiro = novo_candidato(cliente, cabecalho_chefe).json()
    repetido = novo_candidato(cliente, cabecalho_chefe, cpf=primeiro["cpf"])

    assert invalido.status_code == 422
    assert _codigo(invalido) == "CPF_INVALIDO"
    assert repetido.status_code == 409
    assert _codigo(repetido) == "CPF_JA_CADASTRADO"


def test_cadastrar_candidato_recusa_senha_fraca_e_campo_extra(cliente, cabecalho_chefe):
    """TI-28 / RN-05, RN-03: senha curta dá 422 SENHA_INVALIDA; `perfil` no corpo dá 422."""
    senha_fraca = novo_candidato(cliente, cabecalho_chefe, senha="123")
    com_perfil = novo_candidato(cliente, cabecalho_chefe, perfil="CHEFE_SECAO")

    assert senha_fraca.status_code == 422
    assert _codigo(senha_fraca) == "SENHA_INVALIDA"
    assert com_perfil.status_code == 422
    assert _codigo(com_perfil) == "DADOS_INVALIDOS"


def test_listar_candidatos_filtra_por_nome_e_pagina(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-28 / RN-30: o Chefe lista candidatos por nome e com paginação; eleitor recebe 403."""
    novo_candidato(cliente, cabecalho_chefe, nome="Ana Paula Reis")
    novo_candidato(cliente, cabecalho_chefe, nome="Bruno Teixeira")
    novo_candidato(cliente, cabecalho_chefe, nome="Ana Clara Dias")

    todos = cliente.get(ROTA_CANDIDATOS, params={"tamanho": 2}, headers=cabecalho_chefe).json()
    so_ana = cliente.get(ROTA_CANDIDATOS, params={"nome": "ana"}, headers=cabecalho_chefe).json()
    do_eleitor = cliente.get(ROTA_CANDIDATOS, headers=cabecalho_eleitor)

    assert todos["total"] == 3
    assert [c["nome"] for c in todos["itens"]] == ["Ana Clara Dias", "Ana Paula Reis"]
    assert [c["nome"] for c in so_ana["itens"]] == ["Ana Clara Dias", "Ana Paula Reis"]
    assert do_eleitor.status_code == 403


def test_consultar_candidato_por_id(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-28 / RN-30: o Chefe consulta por id; inexistente dá 404; eleitor dá 403."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()

    encontrado = cliente.get(f"{ROTA_CANDIDATOS}/{criado['id']}", headers=cabecalho_chefe)
    inexistente = cliente.get(f"{ROTA_CANDIDATOS}/9999", headers=cabecalho_chefe)
    do_eleitor = cliente.get(f"{ROTA_CANDIDATOS}/{criado['id']}", headers=cabecalho_eleitor)

    assert encontrado.status_code == 200
    assert _mesmos_dados(encontrado.json(), criado)
    assert inexistente.status_code == 404
    assert _codigo(inexistente) == "CANDIDATO_NAO_ENCONTRADO"
    assert do_eleitor.status_code == 403


def test_alterar_candidato_muda_nome_de_urna_e_senha_mas_nao_o_cpf(cliente, cabecalho_chefe):
    """TI-28 / RN-31, RN-33: troca nome de urna e senha; mandar o CPF dá 422."""
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


def test_alterar_candidato_recusa_dados_invalidos_e_id_inexistente(cliente, cabecalho_chefe):
    """TI-28 / RN-31: nome de urna curto e nascimento futuro dão 422; id inexistente dá 404."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()
    rota = f"{ROTA_CANDIDATOS}/{criado['id']}"

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


# ---------------------------------------------------------------- exclusão (TI-29)


def test_excluir_candidato_sem_candidaturas_da_204_e_remove_a_credencial(cliente, cabecalho_chefe):
    """TI-29 / RN-33: excluir candidato sem candidaturas → 204; o login dele deixa de valer."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()
    rota = f"{ROTA_CANDIDATOS}/{criado['id']}"

    resposta = cliente.delete(rota, headers=cabecalho_chefe)

    assert resposta.status_code == 204
    assert cliente.get(rota, headers=cabecalho_chefe).status_code == 404
    assert _entrar(cliente, criado["cpf"], SENHA_CANDIDATO).status_code == 401


def test_excluir_candidato_inexistente_da_404_e_eleitor_nao_exclui(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-29 / RN-30, RN-33: id inexistente dá 404; eleitor tentando excluir dá 403."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()

    inexistente = cliente.delete(f"{ROTA_CANDIDATOS}/9999", headers=cabecalho_chefe)
    do_eleitor = cliente.delete(f"{ROTA_CANDIDATOS}/{criado['id']}", headers=cabecalho_eleitor)

    assert inexistente.status_code == 404
    assert _codigo(inexistente) == "CANDIDATO_NAO_ENCONTRADO"
    assert do_eleitor.status_code == 403


def test_excluir_candidato_com_candidatura_da_409_e_so_depois_de_remover_a_candidatura(
    cliente, cabecalho_chefe
):
    """TI-29 / RN-33: com candidatura → 409 `EXCLUSAO_BLOQUEADA`; sem ela → 204.

    Confirma que a FK `fk_candidaturas_candidato_id_candidatos` tem o nome que o serviço espera:
    se tivesse outro, o erro seria o genérico `CONFLITO_DE_DADOS`.
    """
    nova_eleicao(cliente, cabecalho_chefe)
    candidatura = nova_candidatura(cliente, cabecalho_chefe).json()
    candidato_id = candidatura["candidato"]["id"]
    rota = f"{ROTA_CANDIDATOS}/{candidato_id}"

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
