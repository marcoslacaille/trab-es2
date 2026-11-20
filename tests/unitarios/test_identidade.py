import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.compartilhado.config import obter_configuracao
from app.compartilhado.erros import DadosInvalidos, NaoAutenticado
from app.identidade import senhas, tokens
from app.identidade.dominio import Perfil, validar_senha


@pytest.mark.parametrize(
    "senha",
    [
        pytest.param("1234567", id="7 caracteres"),
        pytest.param("        ", id="so espacos"),
        pytest.param("a" * 73, id="73 bytes"),
        pytest.param("ç" * 37, id="37 caracteres mas 74 bytes"),
    ],
)
def test_recusa_senha_fora_da_regra(senha):
    """TU-07 / RN-05: menos de 8 caracteres, só espaços ou mais de 72 bytes são recusados."""
    with pytest.raises(DadosInvalidos) as erro:
        validar_senha(senha)

    assert erro.value.codigo == "SENHA_INVALIDA"
    assert erro.value.status_http == 422


@pytest.mark.parametrize(
    "senha",
    [
        pytest.param("12345678", id="8 caracteres"),
        pytest.param("a" * 72, id="72 bytes"),
        pytest.param("ç" * 36, id="36 caracteres e 72 bytes"),
    ],
)
def test_aceita_senha_dentro_da_regra(senha):
    """TU-07 / RN-05: a partir de 8 caracteres e até 72 bytes a senha é aceita."""
    validar_senha(senha)


def test_hash_e_diferente_da_senha_e_confere_so_com_a_senha_certa():
    """TU-08 / RN-05: o hash não é a senha, e a conferência dá verdadeiro e falso."""
    senha = "Chefe@2026"

    hash_gerado = senhas.gerar_hash(senha)

    assert hash_gerado != senha
    assert len(hash_gerado) == 60
    assert senhas.senha_confere(senha, hash_gerado) is True
    assert senhas.senha_confere("Chefe@2027", hash_gerado) is False


def test_senha_com_mais_de_72_bytes_nunca_confere_e_nao_da_erro():
    """TU-08 / RN-01, RN-05: o login com senha enorme é só mais uma senha errada (sem 500)."""
    hash_gerado = senhas.gerar_hash("a" * 72)

    assert senhas.senha_confere("a" * 73, hash_gerado) is False


def test_token_de_acesso_criado_e_lido_devolve_o_id_do_usuario():
    """TU-09 / RN-02: criar e ler o token devolve o id; a expiração fica no futuro."""
    token, expira_em = tokens.criar_token_acesso(42, Perfil.ELEITOR)

    assert tokens.ler_token_acesso(token) == 42
    assert expira_em > datetime.now(UTC) + timedelta(minutes=59)


def test_token_adulterado_e_recusado():
    """TU-10 / RN-02: mudar o conteúdo do token invalida a assinatura."""
    token, _ = tokens.criar_token_acesso(42, Perfil.ELEITOR)
    cabecalho, conteudo, assinatura = token.split(".")
    dados = json.loads(base64.urlsafe_b64decode(conteudo + "=" * (-len(conteudo) % 4)))
    dados["sub"] = "1"  # tenta se passar por outro usuário
    conteudo_falso = base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()

    with pytest.raises(NaoAutenticado) as erro:
        tokens.ler_token_acesso(f"{cabecalho}.{conteudo_falso}.{assinatura}")

    assert erro.value.codigo == "TOKEN_INVALIDO"


def test_token_expirado_e_recusado(monkeypatch):
    """TU-11 / RN-02: token emitido com expiração no passado é recusado."""
    monkeypatch.setattr(obter_configuracao(), "jwt_expiracao_minutos", -1)
    token, _ = tokens.criar_token_acesso(42, Perfil.ELEITOR)

    with pytest.raises(NaoAutenticado) as erro:
        tokens.ler_token_acesso(token)

    assert erro.value.codigo == "TOKEN_INVALIDO"


def test_token_de_cedula_nao_serve_como_token_de_acesso():
    """TU-12 / RN-02, RN-57: token válido mas com a audiência da cédula é recusado."""
    token_de_cedula = jwt.encode(
        {
            "sub": "42",
            "aud": "eleicao-api:cedula",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        obter_configuracao().jwt_segredo,
        algorithm="HS256",
    )

    with pytest.raises(NaoAutenticado) as erro:
        tokens.ler_token_acesso(token_de_cedula)

    assert erro.value.codigo == "TOKEN_INVALIDO"
