"""Cédula assinada: a escolha do eleitor fica no token, não no banco (RN-56, RN-57, RN-60).

Só `votacao` conhece este formato. A audiência própria impede usar o token de acesso como
cédula, e vice-versa.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from app.compartilhado.config import obter_configuracao
from app.compartilhado.dominio import Cargo
from app.compartilhado.erros import DadosInvalidos
from app.votacao.dominio import Escolha, TipoVoto

ALGORITMO = "HS256"
AUDIENCIA_CEDULA = "eleicao-api:cedula"


@dataclass(frozen=True)
class Cedula:
    """O conteúdo lido de uma cédula válida."""

    usuario_id: int
    eleicao_id: int
    cargo: Cargo
    tipo: TipoVoto
    candidatura_id: int | None


def emitir_cedula(
    usuario_id: int, eleicao_id: int, cargo: Cargo, escolha: Escolha, agora: datetime
) -> tuple[str, datetime]:
    """Assina a escolha e devolve o token e o instante em que ele expira (RN-56, RN-57, RN-60).

    Nada vai para o banco. A expiração usa o relógio injetável e fica no campo `expira_em`,
    conferido à mão em `ler_cedula` (o `exp` padrão do JWT usaria o relógio real).
    """
    cfg = obter_configuracao()
    expira_em = agora + timedelta(minutes=cfg.cedula_expiracao_minutos)
    dados = {
        "sub": str(usuario_id),
        "aud": AUDIENCIA_CEDULA,
        "eleicao_id": eleicao_id,
        "cargo": cargo.value,
        "tipo": escolha.tipo.value,
        "candidatura_id": escolha.candidatura_id,
        "expira_em": int(expira_em.timestamp()),
    }
    return jwt.encode(dados, cfg.jwt_segredo, algorithm=ALGORITMO), expira_em


def ler_cedula(token: str, agora: datetime) -> Cedula:
    """Confere assinatura, audiência e validade da cédula e devolve o seu conteúdo (RN-57).

    Levanta 422 `CEDULA_INVALIDA` se o token for adulterado, não for uma cédula (por exemplo,
    um token de acesso) ou tiver campos errados, e 422 `CEDULA_EXPIRADA` se passou o prazo.
    """
    cfg = obter_configuracao()
    try:
        dados = jwt.decode(
            token, cfg.jwt_segredo, algorithms=[ALGORITMO], audience=AUDIENCIA_CEDULA
        )
        cedula = Cedula(
            int(dados["sub"]),
            int(dados["eleicao_id"]),
            Cargo(dados["cargo"]),
            TipoVoto(dados["tipo"]),
            dados["candidatura_id"],
        )
        expira_em = int(dados["expira_em"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as erro:
        raise DadosInvalidos("Cédula inválida.", codigo="CEDULA_INVALIDA") from erro
    if agora.timestamp() > expira_em:
        raise DadosInvalidos(
            "Cédula expirada. Registre o voto novamente.", codigo="CEDULA_EXPIRADA"
        )
    return cedula
