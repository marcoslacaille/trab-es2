"""Script `criar_chefe` (RN-04): cria o Chefe da Seção a partir do `.env`, sem expor a senha."""

import pytest
from sqlalchemy import text

from app.compartilhado.banco import SessionLocal
from app.compartilhado.config import obter_configuracao
from app.scripts.criar_chefe import criar_chefe
from tests.auxiliares import CPF_CHEFE


@pytest.fixture
def configurar(monkeypatch):
    """Define as variáveis `CHEFE_*` e limpa o cache da configuração antes e depois."""

    def definir(**variaveis: str) -> None:
        # Variável vazia (e não ausente) também vence o `.env` real do desenvolvedor.
        for nome in ("CHEFE_CPF", "CHEFE_NOME", "CHEFE_SENHA"):
            padrao = "Chefe da Seção" if nome == "CHEFE_NOME" else ""
            monkeypatch.setenv(nome, variaveis.get(nome, padrao))
        obter_configuracao.cache_clear()

    yield definir
    monkeypatch.undo()
    obter_configuracao.cache_clear()


def _quantos_chefes() -> int:
    with SessionLocal() as sessao:
        return sessao.execute(
            text("SELECT COUNT(*) FROM usuarios WHERE perfil = 'CHEFE_SECAO'")
        ).scalar_one()


def test_cria_o_chefe(configurar, capsys):
    """RN-04: com CPF e senha válidos, cria o Chefe e não imprime a senha."""
    configurar(CHEFE_CPF=CPF_CHEFE, CHEFE_SENHA="Chefe@2026")

    resultado = criar_chefe()

    assert resultado == 0 and _quantos_chefes() == 1
    saida = capsys.readouterr().out
    assert "Chefe da Seção criado" in saida and "Chefe@2026" not in saida


def test_e_idempotente(configurar, capsys):
    """RN-04: rodar de novo com o mesmo CPF não cria outro nem altera nada."""
    configurar(CHEFE_CPF=CPF_CHEFE, CHEFE_SENHA="Chefe@2026")
    criar_chefe()

    resultado = criar_chefe()

    assert resultado == 0 and _quantos_chefes() == 1
    assert "nada foi alterado" in capsys.readouterr().out


def test_exige_cpf_e_senha(configurar, capsys):
    """Sem `CHEFE_CPF` ou `CHEFE_SENHA`, avisa e falha (código 1) sem criar ninguém."""
    configurar()

    resultado = criar_chefe()

    assert resultado == 1 and _quantos_chefes() == 0
    assert "Defina CHEFE_CPF e CHEFE_SENHA" in capsys.readouterr().out


@pytest.mark.parametrize(("cpf", "senha"), [("11111111111", "Chefe@2026"), (CPF_CHEFE, "fraca")])
def test_recusa_cpf_ou_senha_invalidos(configurar, capsys, cpf, senha):
    """RN-05 e RN-07: CPF ou senha inválidos falham (código 1), sem criar e sem mostrar a senha."""
    configurar(CHEFE_CPF=cpf, CHEFE_SENHA=senha)

    resultado = criar_chefe()

    assert resultado == 1 and _quantos_chefes() == 0
    saida = capsys.readouterr().out
    assert "Não foi possível criar" in saida and senha not in saida


def test_repassa_conflito_que_nao_e_de_cpf(configurar, monkeypatch):
    """Só `CPF_JA_CADASTRADO` é tratado como "já existe"; qualquer outro conflito sobe."""
    from app.compartilhado.erros import ConflitoDeEstado
    from app.scripts import criar_chefe as script

    def conflito(*argumentos, **nomeados):
        raise ConflitoDeEstado("outro", codigo="OUTRO_CONFLITO")

    configurar(CHEFE_CPF=CPF_CHEFE, CHEFE_SENHA="Chefe@2026")
    monkeypatch.setattr(script.service, "criar_credencial", conflito)

    with pytest.raises(ConflitoDeEstado):
        script.criar_chefe()


def test_executado_como_script_sai_com_o_codigo_da_funcao(configurar):
    """`python -m app.scripts.criar_chefe` termina com `sys.exit(0)` quando deu certo."""
    import runpy

    configurar(CHEFE_CPF=CPF_CHEFE, CHEFE_SENHA="Chefe@2026")

    with pytest.raises(SystemExit) as saida:
        runpy.run_module("app.scripts.criar_chefe", run_name="__main__")

    assert saida.value.code == 0 and _quantos_chefes() == 1
