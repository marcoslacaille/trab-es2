"""Cria o Chefe da Seção inicial (RN-04). Uso: `python -m app.scripts.criar_chefe`.

Lê `CHEFE_CPF`, `CHEFE_NOME` e `CHEFE_SENHA` do `.env`. É idempotente: se o CPF já existe,
não faz nada. Não existe rota para criar Chefe; este script é o único caminho.
"""

import sys

from app.core.config import obter_configuracao
from app.core.database import SessionLocal
from app.core.exceptions import ConflitoDeEstado, DadosInvalidos
from app.core.relogio import agora
from app.identidade import service
from app.models.enums import Perfil


def criar_chefe() -> int:
    """RN-04: cria o Chefe da Seção com os dados do `.env`. Devolve 0 se deu certo, 1 se falhou.

    Valida CPF (RN-07), nome (RN-08) e senha (RN-05) pelo próprio serviço de identidade.
    A mensagem impressa nunca contém a senha.
    """
    configuracao = obter_configuracao()
    if not configuracao.chefe_cpf or not configuracao.chefe_senha:
        print("Defina CHEFE_CPF e CHEFE_SENHA no .env (veja o .env.example).")
        return 1

    with SessionLocal() as sessao:
        try:
            service.criar_credencial(
                sessao,
                cpf=configuracao.chefe_cpf,
                nome=configuracao.chefe_nome,
                senha=configuracao.chefe_senha,
                perfil=Perfil.CHEFE_SECAO,
                agora=agora(),
            )
        except ConflitoDeEstado as erro:
            if erro.codigo != "CPF_JA_CADASTRADO":
                raise
            print("Já existe um usuário com o CPF de CHEFE_CPF; nada foi alterado.")
            return 0
        except DadosInvalidos as erro:
            print(f"Não foi possível criar o Chefe da Seção: {erro.mensagem}")
            return 1
        sessao.commit()

    print(f"Chefe da Seção criado: {configuracao.chefe_nome} (CPF {configuracao.chefe_cpf}).")
    return 0


if __name__ == "__main__":
    sys.exit(criar_chefe())
