"""Token JWT de acesso. Só este módulo conhece o JWT de acesso (ocultação de informação)."""

from datetime import UTC, datetime, timedelta

import jwt

from app.compartilhado.config import obter_configuracao
from app.compartilhado.erros import NaoAutenticado
from app.compartilhado.validadores import MAIOR_ID
from app.identidade.dominio import Perfil

ALGORITMO = "HS256"
# A audiência impede que o token da cédula seja usado como token de acesso, e vice-versa.
AUDIENCIA_ACESSO = "eleicao-api:acesso"


def criar_token_acesso(usuario_id: int, perfil: Perfil) -> tuple[str, datetime]:
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
