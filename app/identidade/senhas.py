"""Hash de senhas com bcrypt. Só este módulo conhece o bcrypt (ocultação de informação)."""

from functools import lru_cache

import bcrypt

from app.compartilhado.config import obter_configuracao
from app.identidade.dominio import BYTES_MAXIMOS_SENHA


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
