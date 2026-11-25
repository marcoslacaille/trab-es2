"""Segurança do `core`: hash bcrypt da senha e token JWT de acesso, sem banco."""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.core import cedula, security
from app.core.config import obter_configuracao
from app.core.exceptions import NaoAutenticado
from app.dto.votacao_dto import Escolha
from app.models.enums import Cargo, Perfil, TipoVoto


def test_hash_nao_e_a_senha_e_so_confere_com_a_senha_certa():
    """RN-05: só o hash é guardado, e ele confere com a senha certa e com mais nenhuma."""
    senha = "Chefe@2026"

    hash_gerado = security.gerar_hash(senha)

    assert hash_gerado != senha
    assert len(hash_gerado) == 60
    assert security.senha_confere(senha, hash_gerado) is True
    assert security.senha_confere("Chefe@2027", hash_gerado) is False
    # RN-01: senha com mais de 72 bytes é só mais uma senha errada, sem erro (sem 500).
    hash_de_72_bytes = security.gerar_hash("a" * 72)
    assert security.senha_confere("a" * 73, hash_de_72_bytes) is False


def test_token_de_acesso_criado_e_lido_devolve_o_id_do_usuario():
    """RN-02: criar e ler o token devolve o id; a expiração fica no futuro."""
    token, expira_em = security.criar_token_acesso(42, Perfil.ELEITOR)

    assert security.ler_token_acesso(token) == 42
    assert expira_em > datetime.now(UTC) + timedelta(minutes=59)


def _adulterar(token: str) -> str:
    """Troca o `sub` do conteúdo por outro usuário, mantendo a assinatura antiga."""
    cabecalho, conteudo, assinatura = token.split(".")
    dados = json.loads(base64.urlsafe_b64decode(conteudo + "=" * (-len(conteudo) % 4)))
    dados["sub"] = "1"  # tenta se passar por outro usuário
    conteudo_falso = base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()
    return f"{cabecalho}.{conteudo_falso}.{assinatura}"


@pytest.mark.parametrize("defeito", ["adulterado", "expirado"])
def test_token_adulterado_ou_expirado_e_recusado(defeito, monkeypatch):
    """RN-02: mudar o conteúdo invalida a assinatura, e o token vencido não vale."""
    if defeito == "expirado":
        monkeypatch.setattr(obter_configuracao(), "jwt_expiracao_minutos", -1)
    token, _ = security.criar_token_acesso(42, Perfil.ELEITOR)
    if defeito == "adulterado":
        token = _adulterar(token)

    with pytest.raises(NaoAutenticado) as erro:
        security.ler_token_acesso(token)

    assert erro.value.codigo == "TOKEN_INVALIDO"


def test_token_de_cedula_nao_serve_como_token_de_acesso():
    """RN-02 e RN-57: uma cédula de verdade, emitida pela votação, não é token de acesso."""
    token_de_cedula, _ = cedula.emitir_cedula(
        42, 7, Cargo.PRESIDENTE, Escolha(TipoVoto.BRANCO), datetime.now(UTC)
    )

    with pytest.raises(NaoAutenticado) as erro:
        security.ler_token_acesso(token_de_cedula)

    assert erro.value.codigo == "TOKEN_INVALIDO"
