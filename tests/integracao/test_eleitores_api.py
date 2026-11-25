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


def test_cadastrar_devolve_201_sem_senha_e_eleitor_consegue_entrar(
    cliente, cabecalho_chefe, relogio
):
    """TI-18 / RN-20, RN-07: cadastra com CPF pontuado, não devolve senha e o login funciona."""
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


def test_cadastrar_exige_perfil_chefe(cliente, cabecalho_eleitor):
    """TI-18 / RN-20: o eleitor não cadastra outros eleitores."""
    resposta = novo_eleitor(cliente, cabecalho_eleitor)

    assert resposta.status_code == 403
    assert _codigo(resposta) == "PERFIL_NAO_AUTORIZADO"


def test_cadastrar_recusa_cpf_invalido(cliente, cabecalho_chefe):
    """TI-19 / RN-07: CPF com dígitos verificadores errados dá 422 CPF_INVALIDO."""
    resposta = novo_eleitor(cliente, cabecalho_chefe, cpf="111.111.111-11")

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CPF_INVALIDO"


def test_cadastrar_recusa_cpf_repetido_de_outro_eleitor(cliente, cabecalho_chefe):
    """TI-19 / RN-07: CPF já usado por um eleitor dá 409 CPF_JA_CADASTRADO."""
    primeiro = novo_eleitor(cliente, cabecalho_chefe).json()

    resposta = novo_eleitor(cliente, cabecalho_chefe, cpf=primeiro["cpf"])

    assert resposta.status_code == 409
    assert _codigo(resposta) == "CPF_JA_CADASTRADO"


def test_cadastrar_recusa_cpf_repetido_de_um_candidato(cliente, cabecalho_chefe):
    """TI-19 / RN-07: o CPF é único entre todos os usuários, inclusive os candidatos."""
    cpf = gerar_cpf(900)
    _criar_candidato(cpf)

    resposta = novo_eleitor(cliente, cabecalho_chefe, cpf=cpf)

    assert resposta.status_code == 409
    assert _codigo(resposta) == "CPF_JA_CADASTRADO"


def test_cadastrar_recusa_titulo_repetido(cliente, cabecalho_chefe):
    """TI-19 / RN-21: título já usado dá 409 TITULO_JA_CADASTRADO, sem criar a credencial."""
    primeiro = novo_eleitor(cliente, cabecalho_chefe).json()
    cpf_novo = gerar_cpf(901)

    resposta = novo_eleitor(
        cliente, cabecalho_chefe, cpf=cpf_novo, titulo_eleitor=primeiro["titulo_eleitor"]
    )

    assert resposta.status_code == 409
    assert _codigo(resposta) == "TITULO_JA_CADASTRADO"
    assert _entrar(cliente, cpf_novo, SENHA_ELEITOR).status_code == 401


def test_cadastrar_recusa_titulo_com_tamanho_ou_formato_errado(cliente, cabecalho_chefe):
    """TI-19 / RN-21: título precisa ter 12 dígitos; 11 dígitos ou letras dão 422."""
    curto = novo_eleitor(cliente, cabecalho_chefe, titulo_eleitor="12345678901")
    com_letra = novo_eleitor(cliente, cabecalho_chefe, titulo_eleitor="12345678901a")

    assert curto.status_code == 422
    assert _codigo(curto) == "DADOS_INVALIDOS"
    assert com_letra.status_code == 422
    assert _codigo(com_letra) == "DADOS_INVALIDOS"


def test_cadastrar_recusa_menor_de_16_anos(cliente, cabecalho_chefe):
    """TI-20 / RN-22: um dia antes dos 16 anos completos dá 422 IDADE_MINIMA."""
    cpf = gerar_cpf(902)

    resposta = novo_eleitor(cliente, cabecalho_chefe, cpf=cpf, data_nascimento="2010-11-26")

    assert resposta.status_code == 422
    assert _codigo(resposta) == "IDADE_MINIMA"
    assert _entrar(cliente, cpf, SENHA_ELEITOR).status_code == 401


def test_cadastrar_aceita_quem_faz_16_anos_hoje(cliente, cabecalho_chefe):
    """TI-20 / RN-22: com 16 anos completos na data do cadastro (25/11/2026) pode."""
    resposta = novo_eleitor(cliente, cabecalho_chefe, data_nascimento="2010-11-25")

    assert resposta.status_code == 201


def test_cadastrar_recusa_campo_extra_perfil(cliente, cabecalho_chefe):
    """TI-21 / RN-23: mandar `perfil` no corpo dá 422 (extra="forbid")."""
    resposta = novo_eleitor(cliente, cabecalho_chefe, perfil="CHEFE_SECAO")

    corpo = resposta.json()["erro"]
    assert resposta.status_code == 422
    assert corpo["codigo"] == "DADOS_INVALIDOS"
    assert corpo["detalhes"]["campos"][0]["campo"] == "perfil"


def test_alterar_nome_e_senha_e_a_nova_senha_funciona(cliente, cabecalho_chefe):
    """TI-22 / RN-23: altera nome e senha; a senha antiga deixa de valer, a nova funciona."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()

    resposta = cliente.patch(
        f"{ROTA}/{eleitor['id']}",
        json={"nome": "Nome Novo da Silva", "senha": "NovaSenha@456"},
        headers=cabecalho_chefe,
    )

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Nome Novo da Silva"
    assert resposta.json()["cpf"] == eleitor["cpf"]
    assert _entrar(cliente, eleitor["cpf"], SENHA_ELEITOR).status_code == 401
    assert _entrar(cliente, eleitor["cpf"], "NovaSenha@456").status_code == 200


def test_alterar_data_de_nascimento_passa_pela_regra_de_idade(cliente, cabecalho_chefe):
    """TI-22 / RN-22, RN-23: a nova data de nascimento também precisa de 16 anos completos."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()

    valida = cliente.patch(
        f"{ROTA}/{eleitor['id']}", json={"data_nascimento": "2000-01-31"}, headers=cabecalho_chefe
    )
    menor = cliente.patch(
        f"{ROTA}/{eleitor['id']}", json={"data_nascimento": "2015-01-01"}, headers=cabecalho_chefe
    )

    assert valida.status_code == 200
    assert valida.json()["data_nascimento"] == "2000-01-31"
    assert menor.status_code == 422
    assert _codigo(menor) == "IDADE_MINIMA"


def test_alterar_cpf_ou_titulo_da_422(cliente, cabecalho_chefe):
    """TI-22 / RN-23: CPF e título não mudam depois do cadastro."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()

    com_cpf = cliente.patch(
        f"{ROTA}/{eleitor['id']}", json={"cpf": gerar_cpf(903)}, headers=cabecalho_chefe
    )
    com_titulo = cliente.patch(
        f"{ROTA}/{eleitor['id']}", json={"titulo_eleitor": "999999999999"}, headers=cabecalho_chefe
    )

    assert com_cpf.status_code == 422
    assert _codigo(com_cpf) == "DADOS_INVALIDOS"
    assert com_titulo.status_code == 422
    assert _codigo(com_titulo) == "DADOS_INVALIDOS"


def test_excluir_eleitor_que_nao_votou_apaga_tambem_a_credencial(cliente, cabecalho_chefe):
    """TI-23 / RN-24: exclui com 204, o login dele falha e a consulta dá 404."""
    eleitor = novo_eleitor(cliente, cabecalho_chefe).json()

    resposta = cliente.delete(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe)

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert _entrar(cliente, eleitor["cpf"], SENHA_ELEITOR).status_code == 401
    consulta = cliente.get(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe)
    assert consulta.status_code == 404
    assert _codigo(consulta) == "ELEITOR_NAO_ENCONTRADO"


def test_excluir_eleitor_que_ja_votou_da_409(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-24 / RN-24: quem já votou não pode ser excluído (409 `EXCLUSAO_BLOQUEADA`)."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201
    eleitor = cliente.get(f"{ROTA}/eu", headers=cabecalho_eleitor).json()

    resposta = cliente.delete(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert _codigo(resposta) == "EXCLUSAO_BLOQUEADA"
    assert cliente.get(f"{ROTA}/{eleitor['id']}", headers=cabecalho_chefe).status_code == 200


def test_listar_filtra_por_nome_e_pagina(cliente, cabecalho_chefe):
    """TI-25 / RN-20: filtro por nome, ordem por nome e `total`, `pagina`, `tamanho`."""
    for nome in ("Ana Souza", "Bruno Lima", "Ana Paula Dias"):
        assert novo_eleitor(cliente, cabecalho_chefe, nome=nome).status_code == 201

    filtrada = cliente.get(ROTA, params={"nome": "ANA"}, headers=cabecalho_chefe).json()
    segunda = cliente.get(ROTA, params={"pagina": 2, "tamanho": 1}, headers=cabecalho_chefe).json()

    assert [e["nome"] for e in filtrada["itens"]] == ["Ana Paula Dias", "Ana Souza"]
    assert filtrada["total"] == 2
    assert [e["nome"] for e in segunda["itens"]] == ["Ana Souza"]
    assert (segunda["pagina"], segunda["tamanho"], segunda["total"]) == (2, 1, 3)


def test_listar_nao_mostra_senha_nem_usuarios_de_outros_perfis(cliente, cabecalho_chefe):
    """TI-25 / RN-20: a lista traz só eleitores (o Chefe não aparece) e nunca a senha."""
    novo_eleitor(cliente, cabecalho_chefe)

    corpo = cliente.get(ROTA, headers=cabecalho_chefe).json()

    assert corpo["total"] == 1
    assert "senha" not in corpo["itens"][0]


def test_eleitor_nao_lista_nem_consulta_outros_eleitores(cliente, cabecalho_eleitor):
    """RN-20 (complementa TI-25): só o Chefe lista e consulta; o eleitor recebe 403."""
    listagem = cliente.get(ROTA, headers=cabecalho_eleitor)
    consulta = cliente.get(f"{ROTA}/1", headers=cabecalho_eleitor)

    assert listagem.status_code == 403
    assert _codigo(listagem) == "PERFIL_NAO_AUTORIZADO"
    assert consulta.status_code == 403


def test_consultar_eleitor_inexistente_da_404(cliente, cabecalho_chefe):
    """RN-20 (complementa TI-25): id que não existe dá 404 ELEITOR_NAO_ENCONTRADO."""
    resposta = cliente.get(f"{ROTA}/999", headers=cabecalho_chefe)

    assert resposta.status_code == 404
    assert _codigo(resposta) == "ELEITOR_NAO_ENCONTRADO"


def test_eleitor_ve_os_proprios_dados_em_eleitores_eu(cliente, cabecalho_chefe):
    """TI-26 / RN-25: `/eleitores/eu` devolve os dados do eleitor logado, não os de outro."""
    outro = novo_eleitor(cliente, cabecalho_chefe, nome="Outro Eleitor").json()
    meu = novo_eleitor(cliente, cabecalho_chefe, nome="Meu Nome Completo").json()
    cabecalho = login(cliente, meu["cpf"], SENHA_ELEITOR)

    resposta = cliente.get(f"{ROTA}/eu", headers=cabecalho)

    corpo = resposta.json()
    assert resposta.status_code == 200
    assert corpo["id"] == meu["id"] != outro["id"]
    assert corpo["nome"] == "Meu Nome Completo"
    assert corpo["cpf"] == meu["cpf"]
    assert corpo["titulo_eleitor"] == meu["titulo_eleitor"]
    # O banco devolve o horário em outro fuso; o instante é o mesmo.
    assert datetime.fromisoformat(corpo["criado_em"]) == datetime.fromisoformat(meu["criado_em"])


def test_eleitores_eu_so_para_eleitor(cliente, cabecalho_chefe):
    """TI-26 / RN-25: o Chefe em `/eleitores/eu` recebe 403, e sem token, 401."""
    chefe = cliente.get(f"{ROTA}/eu", headers=cabecalho_chefe)
    anonimo = cliente.get(f"{ROTA}/eu")

    assert chefe.status_code == 403
    assert _codigo(chefe) == "PERFIL_NAO_AUTORIZADO"
    assert anonimo.status_code == 401
