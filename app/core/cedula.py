"""Cédula cifrada: a escolha do eleitor fica no token, não no banco (RN-56, RN-57, RN-60).

Só `votacao` conhece este formato. A cédula é cifrada e autenticada com Fernet (D-144): quem
tiver o token, sem a chave, não lê nem o eleitor nem a escolha, e qualquer alteração o invalida.
A chave é derivada do `JWT_SEGREDO` com um contexto próprio, então é diferente da chave do token
de acesso: um não serve no lugar do outro.
"""

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import obter_configuracao
from app.core.exceptions import DadosInvalidos
from app.dto.votacao_dto import Escolha
from app.models.enums import Cargo, TipoVoto

CONTEXTO_DA_CHAVE = b"eleicao-api:cedula"


@dataclass(frozen=True)
class Cedula:
    """O conteúdo lido de uma cédula válida."""

    usuario_id: int
    eleicao_id: int
    cargo: Cargo
    tipo: TipoVoto
    candidatura_id: int | None


def _cifrador() -> Fernet:
    """O Fernet da cédula, com a chave derivada do `JWT_SEGREDO` pelo HKDF (D-144)."""
    segredo = obter_configuracao().jwt_segredo.encode("utf-8")
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXTO_DA_CHAVE).derive(
        segredo
    )
    return Fernet(base64.urlsafe_b64encode(chave))


def emitir_cedula(
    usuario_id: int, eleicao_id: int, cargo: Cargo, escolha: Escolha, agora: datetime
) -> tuple[str, datetime]:
    """Cifra a escolha e devolve o token e o instante em que ele expira (RN-56, RN-57, RN-60).

    Nada vai para o banco. A expiração usa o relógio injetável e fica dentro do conteúdo cifrado
    (`expira_em`, com a mesma precisão devolvida ao eleitor), conferida em `ler_cedula`.
    """
    expira_em = agora + timedelta(minutes=obter_configuracao().cedula_expiracao_minutos)
    dados = {
        "usuario_id": usuario_id,
        "eleicao_id": eleicao_id,
        "cargo": cargo.value,
        "tipo": escolha.tipo.value,
        "candidatura_id": escolha.candidatura_id,
        "expira_em": expira_em.isoformat(),
    }
    token = _cifrador().encrypt(json.dumps(dados).encode("utf-8")).decode("ascii")
    return token, expira_em


def ler_cedula(token: str, agora: datetime) -> Cedula:
    """Decifra a cédula, confere o conteúdo e a validade e devolve os dados (RN-57).

    Levanta 422 `CEDULA_INVALIDA` se o token for adulterado, não for uma cédula (por exemplo,
    um token de acesso) ou tiver campos errados, e 422 `CEDULA_EXPIRADA` se passou o prazo.
    """
    try:
        dados = json.loads(_cifrador().decrypt(token.encode("utf-8")))
        cedula = Cedula(
            int(dados["usuario_id"]),
            int(dados["eleicao_id"]),
            Cargo(dados["cargo"]),
            TipoVoto(dados["tipo"]),
            dados["candidatura_id"],
        )
        expira_em = datetime.fromisoformat(dados["expira_em"])
    except (InvalidToken, KeyError, ValueError, TypeError) as erro:
        raise DadosInvalidos("Cédula inválida.", codigo="CEDULA_INVALIDA") from erro
    if agora > expira_em:
        raise DadosInvalidos(
            "Cédula expirada. Registre o voto novamente.", codigo="CEDULA_EXPIRADA"
        )
    return cedula
