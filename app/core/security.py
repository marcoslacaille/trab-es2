"""Segurança: hash de senha (bcrypt) e token JWT de acesso. Só este arquivo conhece os dois."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING

import bcrypt
import jwt

from app.core.config import obter_configuracao
from app.core.exceptions import NaoAutenticado
from app.core.validadores import MAIOR_ID

if TYPE_CHECKING:
    # Só para a anotação de `criar_token_acesso`.
    from app.models.enums import Perfil

# Limite do bcrypt: ele só lê os 72 primeiros bytes e as versões recentes recusam senhas maiores.
BYTES_MAXIMOS_SENHA = 72

ALGORITMO = "HS256"
# A audiência impede que o token da cédula seja usado como token de acesso, e vice-versa.
AUDIENCIA_ACESSO = "eleicao-api:acesso"


def gerar_hash(senha: str) -> str:
    """Gera o hash bcrypt da senha. A senha em si nunca é gravada (RN-05)."""
    custo = obter_configuracao().bcrypt_custo
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=custo)).decode("utf-8")


def senha_confere(senha: str, senha_hash: str) -> bool:
    """Diz se a senha corresponde ao hash (RN-01).

    Senha com mais de 72 bytes nunca confere (nenhuma senha assim é aceita no cadastro, RN-05).
    O bcrypt recusa esse tamanho com erro, então a comparação é feita mesmo assim, só para
    gastar o mesmo tempo, e o resultado é sempre falso.
    """
    dados = senha.encode("utf-8")
    if len(dados) > BYTES_MAXIMOS_SENHA:
        bcrypt.checkpw(dados[:BYTES_MAXIMOS_SENHA], senha_hash.encode("utf-8"))
        return False
    return bcrypt.checkpw(dados, senha_hash.encode("utf-8"))


@lru_cache
def hash_ficticio() -> str:
    """Hash usado quando o CPF não existe, para o login demorar o mesmo tempo (RN-01)."""
    return gerar_hash("senha-que-nao-pertence-a-ninguem")


def criar_token_acesso(usuario_id: int, perfil: "Perfil") -> tuple[str, datetime]:
    """Emite o token de acesso (RN-02). Devolve o token e o instante em que ele expira.

    O `perfil` vai no token só como informação: a autorização usa o perfil do banco.
    """
    configuracao = obter_configuracao()
    # Relógio real (e não o injetável): o JWT é validado pela biblioteca com o relógio real.
    emitido_em = datetime.now(UTC)
    expira_em = emitido_em + timedelta(minutes=configuracao.jwt_expiracao_minutos)
    dados = {
        "sub": str(usuario_id),  # o PyJWT exige texto
        "perfil": perfil.value,
        "aud": AUDIENCIA_ACESSO,
        "iat": emitido_em,
        "exp": expira_em,
    }
    token = jwt.encode(dados, configuracao.jwt_segredo, algorithm=ALGORITMO)
    return token, expira_em


def ler_token_acesso(token: str) -> int:
    """Valida assinatura, audiência e expiração (RN-02). Devolve o ID do usuário.

    Levanta `NaoAutenticado` (`TOKEN_INVALIDO`, 401) se o token não servir.
    """
    configuracao = obter_configuracao()
    try:
        dados = jwt.decode(
            token,
            configuracao.jwt_segredo,
            algorithms=[ALGORITMO],  # explícito: bloqueia o truque do `alg: none`
            audience=AUDIENCIA_ACESSO,
            options={"require": ["sub", "exp", "aud"]},
        )
        usuario_id = int(dados["sub"])
        if not 0 < usuario_id <= MAIOR_ID:  # fora da faixa do BIGINT, o banco daria erro 500
            raise ValueError("sub fora da faixa de IDs")
        return usuario_id
    except (jwt.InvalidTokenError, ValueError) as erro:
        raise NaoAutenticado("Token inválido ou expirado.", codigo="TOKEN_INVALIDO") from erro
