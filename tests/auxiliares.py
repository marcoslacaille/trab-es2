"""Fábricas de dados e helpers de login para os testes."""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.relogio import agora
from app.models.enums import Perfil
from app.services.usuario_service import UsuarioService

CPF_CHEFE = "29141777638"
SENHA_CHEFE = "Chefe@2026"
SENHA_ELEITOR = "Eleitor@123"
SENHA_CANDIDATO = "Candidato@123"

# Cada chamada de `novo_eleitor` pega o próximo número, para CPF e título nunca se repetirem.
_sequencia_de_eleitores = count(1)
# Mesma ideia para candidatos (semente de CPF diferente da dos eleitores) e para partidos.
_sequencia_de_candidatos = count(5_000)
_sequencia_de_partidos = count(10)


def _digito_verificador(nove_ou_dez_digitos: str) -> str:
    """Calcula um dígito verificador do CPF (mesmo algoritmo de `cpf_valido`)."""
    tamanho = len(nove_ou_dez_digitos)
    soma = sum(int(nove_ou_dez_digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
    return str((soma * 10) % 11 % 10)


def gerar_cpf(semente: int) -> str:
    """CPF válido e determinístico: a mesma semente sempre dá o mesmo CPF (só dígitos)."""
    while True:
        base = str(100_000_000 + semente)
        cpf = base + _digito_verificador(base)
        cpf += _digito_verificador(cpf)
        if cpf != cpf[0] * 11:  # CPF com todos os dígitos iguais é inválido (RN-07)
            return cpf
        semente += 1


def criar_chefe() -> int:
    """Cria o Chefe da Seção direto pelo serviço de identidade, com commit. Devolve o id."""
    with SessionLocal() as sessao:
        usuario_id = UsuarioService(sessao).criar_credencial(
            CPF_CHEFE, "Chefe da Seção", SENHA_CHEFE, Perfil.CHEFE_SECAO, agora()
        )
        sessao.commit()
    return usuario_id


def login(cliente: TestClient, cpf: str, senha: str) -> dict[str, str]:
    """Faz login pela API e devolve o cabeçalho `{"Authorization": "Bearer ..."}`."""
    resposta = cliente.post("/api/v1/auth/login", data={"username": cpf, "password": senha})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


@pytest.fixture
def cabecalho_chefe(cliente: TestClient) -> dict[str, str]:
    """Cria o Chefe da Seção e devolve o cabeçalho de autenticação dele."""
    criar_chefe()
    return login(cliente, CPF_CHEFE, SENHA_CHEFE)


def novo_eleitor(cliente: TestClient, cabecalho: dict[str, str], **sobrescritas):
    """Cadastra um eleitor pela API com dados válidos e devolve a resposta HTTP.

    Cada chamada usa um CPF e um título novos. A senha padrão é `SENHA_ELEITOR`. Os testes
    passam `sobrescritas` para provocar erros (ex.: `data_nascimento="2015-01-01"`), por isso a
    resposta vem sem nenhuma conferência de status.
    """
    numero = next(_sequencia_de_eleitores)
    dados = {
        "nome": f"Eleitor de Teste {numero}",
        "cpf": gerar_cpf(numero),
        "titulo_eleitor": str(100_000_000_000 + numero),
        "data_nascimento": "1990-04-12",
        "senha": SENHA_ELEITOR,
    }
    dados.update(sobrescritas)
    return cliente.post("/api/v1/eleitores", json=dados, headers=cabecalho)


@pytest.fixture
def cabecalho_eleitor(cliente: TestClient, cabecalho_chefe: dict[str, str]) -> dict[str, str]:
    """Cadastra um eleitor (pelo Chefe) e devolve o cabeçalho de autenticação dele."""
    resposta = novo_eleitor(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_ELEITOR)


def novo_partido(cliente: TestClient, cabecalho: dict[str, str], **sobrescritas):
    """Cadastra um partido pela API com dados válidos e devolve a resposta HTTP.

    Cada chamada usa um número (10, 11, ...), uma sigla e um nome novos. Os testes passam
    `sobrescritas` para provocar erros (ex.: `numero=10` repetido), por isso a resposta vem sem
    nenhuma conferência de status.

    Sem `sobrescritas`, se o número gerado já existir no teste (o contador dá a volta em 90 e
    pode cair num partido criado à mão, como o 10), tenta o próximo. Assim o resultado não
    depende da ordem em que os testes rodam.
    """
    for _ in range(90):
        # O contador vale para a sessão de testes toda; o número do partido vai de 10 a 99.
        numero = 10 + (next(_sequencia_de_partidos) - 10) % 90
        dados = {"sigla": f"P{numero}", "nome": f"Partido de Teste {numero}", "numero": numero}
        dados.update(sobrescritas)
        resposta = cliente.post("/api/v1/partidos", json=dados, headers=cabecalho)
        if sobrescritas or resposta.status_code != 409:
            return resposta
    return resposta


def novo_candidato(cliente: TestClient, cabecalho: dict[str, str], **sobrescritas):
    """Cadastra um candidato pela API com dados válidos e devolve a resposta HTTP.

    Cada chamada usa um CPF e um nome novos. A senha padrão é `SENHA_CANDIDATO`. Os testes
    passam `sobrescritas` para provocar erros (ex.: `nome_urna="Jo"`), por isso a resposta vem
    sem nenhuma conferência de status.
    """
    numero = next(_sequencia_de_candidatos)
    dados = {
        "nome": f"Candidato de Teste {numero}",
        "nome_urna": f"Candidato {numero}",
        "cpf": gerar_cpf(numero),
        "data_nascimento": "1968-03-05",
        "senha": SENHA_CANDIDATO,
    }
    dados.update(sobrescritas)
    return cliente.post("/api/v1/candidatos", json=dados, headers=cabecalho)


@pytest.fixture
def cabecalho_candidato(cliente: TestClient, cabecalho_chefe: dict[str, str]) -> dict[str, str]:
    """Cadastra um candidato (pelo Chefe) e devolve o cabeçalho de autenticação dele."""
    resposta = novo_candidato(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_CANDIDATO)


def nova_eleicao(cliente: TestClient, cabecalho: dict[str, str], **sobrescritas):
    """Cria uma eleição pela API com dados válidos e devolve a resposta HTTP.

    Por padrão: 25/11/2026 (o dia do relógio de teste), 1º turno, das 08:00 às 17:00. Os testes
    passam `sobrescritas` para provocar erros (ex.: `turno=2`), por isso a resposta vem sem
    nenhuma conferência de status.
    """
    dados = {
        "descricao": "Eleições Gerais 2026 — 1º turno",
        "data": "2026-11-25",
        "turno": 1,
        "horario_abertura": "08:00",
        "horario_encerramento": "17:00",
    }
    dados.update(sobrescritas)
    return cliente.post("/api/v1/eleicoes", json=dados, headers=cabecalho)


def nova_candidatura(
    cliente: TestClient, cabecalho: dict[str, str], eleicao_id: int = 1, **sobrescritas
):
    """Cria uma candidatura pela API e devolve a resposta HTTP.

    Por padrão: Presidente, número `10`, e um candidato e um partido novos (criados pela API
    com o mesmo cabeçalho, que precisa ser o do Chefe). Os testes passam `sobrescritas`
    (`candidato_id`, `partido_id`, `cargo`, `numero`) para provocar erros, por isso a resposta
    vem sem nenhuma conferência de status.
    """
    dados = dict(sobrescritas)
    if "candidato_id" not in dados:
        candidato = novo_candidato(cliente, cabecalho)
        assert candidato.status_code == 201, candidato.text
        dados["candidato_id"] = candidato.json()["id"]
    if "partido_id" not in dados:
        partido = novo_partido(cliente, cabecalho)
        assert partido.status_code == 201, partido.text
        dados["partido_id"] = partido.json()["id"]
    dados.setdefault("cargo", "PRESIDENTE")
    dados.setdefault("numero", "10")
    return cliente.post(
        f"/api/v1/eleicoes/{eleicao_id}/candidaturas", json=dados, headers=cabecalho
    )


def eleicao_aberta_com_candidatos(cliente: TestClient, cabecalho_chefe: dict[str, str]) -> dict:
    """Eleição de 25/11/2026 (08:00 às 17:00), com candidaturas, já ABERTA (relógio às 10:00).

    Presidente 10 e 20, Senador 101 e 202, todos por um mesmo partido. Devolve os ids:
    `{"eleicao_id": 1, "candidaturas": {"PRESIDENTE": {"10": 1, "20": 2},
    "SENADOR": {"101": 3, "202": 4}}}`.
    """
    eleicao = nova_eleicao(cliente, cabecalho_chefe)
    assert eleicao.status_code == 201, eleicao.text
    eleicao_id = eleicao.json()["id"]
    partido = novo_partido(cliente, cabecalho_chefe)
    assert partido.status_code == 201, partido.text
    partido_id = partido.json()["id"]
    candidaturas: dict[str, dict[str, int]] = {}
    for cargo, numero in [
        ("PRESIDENTE", "10"),
        ("PRESIDENTE", "20"),
        ("SENADOR", "101"),
        ("SENADOR", "202"),
    ]:
        resposta = nova_candidatura(
            cliente, cabecalho_chefe, eleicao_id, partido_id=partido_id, cargo=cargo, numero=numero
        )
        assert resposta.status_code == 201, resposta.text
        candidaturas.setdefault(cargo, {})[numero] = resposta.json()["id"]
    abertura = cliente.post(f"/api/v1/eleicoes/{eleicao_id}/abertura", headers=cabecalho_chefe)
    assert abertura.status_code == 200, abertura.text
    return {"eleicao_id": eleicao_id, "candidaturas": candidaturas}


def votar(
    cliente: TestClient,
    cabecalho: dict[str, str],
    eleicao_id: int,
    cargo: str,
    numero: str | None = None,
    branco: bool = False,
):
    """Vota em dois passos (registro e confirmação) e devolve a resposta da confirmação.

    Com `branco=True` usa o modo BRANCO; senão digita o `numero`. Se o registro falhar,
    devolve a resposta do registro (os testes conferem o status e o código do erro).
    """
    pedido = {"cargo": cargo, "modo": "BRANCO" if branco else "NUMERO"}
    if not branco:
        pedido["numero"] = numero
    base = f"/api/v1/votacao/eleicoes/{eleicao_id}/votos"
    registro = cliente.post(f"{base}/registro", json=pedido, headers=cabecalho)
    if registro.status_code != 200:
        return registro
    return cliente.post(
        f"{base}/confirmacao",
        json={"token_cedula": registro.json()["token_cedula"]},
        headers=cabecalho,
    )
