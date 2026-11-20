"""Fábricas de dados e helpers de login para os testes (seção 12 do PLANO)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.compartilhado.banco import SessionLocal
from app.compartilhado.relogio import agora
from app.identidade import servico
from app.identidade.dominio import Perfil

CPF_CHEFE = "29141777638"
SENHA_CHEFE = "Chefe@2026"


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


def criar_chefe(
    cpf: str = CPF_CHEFE, senha: str = SENHA_CHEFE, agora_: datetime | None = None
) -> int:
    """Cria o Chefe da Seção direto pelo serviço de identidade, com commit. Devolve o id."""
    with SessionLocal() as sessao:
        usuario_id = servico.criar_credencial(
            sessao, cpf, "Chefe da Seção", senha, Perfil.CHEFE_SECAO, agora_ or agora()
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
