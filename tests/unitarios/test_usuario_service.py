"""Testes do `UsuarioService`: regra da senha, login e credenciais, com o repository falso."""

from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from app.core import security
from app.core.exceptions import ConflitoDeEstado, DadosInvalidos, NaoAutenticado
from app.dto.usuario_dto import UsuarioAutenticado
from app.models.enums import Perfil
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.services.usuario_service import UsuarioService, validar_senha

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
SENHA = "Chefe@2026"


def um_service() -> UsuarioService:
    """O service com repository e sessão falsos: nada chega ao banco."""
    return UsuarioService(sessao=Mock(), repository=Mock(spec=UsuarioRepository))


def um_usuario_gravado() -> Usuario:
    """O Chefe como o repository o devolveria, com o hash bcrypt de `SENHA`."""
    return Usuario(
        id=1,
        cpf="52998224725",
        nome="Chefe da Seção",
        senha_hash=security.gerar_hash(SENHA),
        perfil=Perfil.CHEFE_SECAO.value,
        criado_em=AGORA,
        atualizado_em=AGORA,
    )


@pytest.mark.parametrize(
    ("recusadas", "aceita"),
    [
        pytest.param(["1234567", "        "], "12345678", id="curta-ou-so-espacos"),
        pytest.param(["a" * 73, "ç" * 37], "ç" * 36, id="mais-de-72-bytes"),  # 36 × 2 = 72 bytes
    ],
)
def test_senha_fora_da_regra_e_recusada(recusadas, aceita):
    """RN-05: menos de 8 caracteres, só espaços ou mais de 72 bytes são recusados (422)."""
    for senha in recusadas:
        with pytest.raises(DadosInvalidos) as erro:
            validar_senha(senha)

        assert erro.value.codigo == "SENHA_INVALIDA", senha
        assert erro.value.status_http == 422
    validar_senha(aceita)  # o limite de cada lado passa


def test_atualizar_credencial_recusa_nome_curto_e_senha_fraca():
    """RN-05 e RN-08: nome curto e senha fraca são recusados; trocar só o nome mantém a senha."""
    service = um_service()
    usuario = um_usuario_gravado()
    service.repository.buscar_por_id.return_value = usuario
    hash_antigo = usuario.senha_hash

    with pytest.raises(DadosInvalidos) as nome_curto:
        service.atualizar_credencial(1, AGORA, nome=" ab ")
    with pytest.raises(DadosInvalidos) as senha_fraca:
        service.atualizar_credencial(1, AGORA, senha="fraca")

    assert nome_curto.value.codigo == "DADOS_INVALIDOS"
    assert senha_fraca.value.codigo == "SENHA_INVALIDA"
    assert (usuario.nome, usuario.senha_hash) == ("Chefe da Seção", hash_antigo)

    service.atualizar_credencial(1, AGORA, nome="  Outro Nome ")

    assert usuario.nome == "Outro Nome"
    assert usuario.senha_hash == hash_antigo


def test_autenticar_devolve_token_e_perfil():
    """RN-01: CPF e senha certos devolvem o token do usuário e o perfil dele, sem commit."""
    service = um_service()
    service.repository.buscar_por_cpf.return_value = um_usuario_gravado()

    resultado = service.autenticar("529.982.247-25", SENHA)

    service.repository.buscar_por_cpf.assert_called_once_with("52998224725")  # CPF normalizado
    assert security.ler_token_acesso(resultado.access_token) == 1
    assert resultado.usuario == UsuarioAutenticado(
        id=1, nome="Chefe da Seção", cpf="52998224725", perfil=Perfil.CHEFE_SECAO
    )
    service.sessao.commit.assert_not_called()


def test_autenticar_nao_distingue_cpf_inexistente_de_senha_errada():
    """RN-01: senha errada, CPF inexistente e CPF mal formatado dão o mesmo 401."""
    service = um_service()
    usuario = um_usuario_gravado()
    service.repository.buscar_por_cpf.side_effect = lambda cpf: (
        usuario if cpf == usuario.cpf else None
    )
    tentativas = [
        ("529.982.247-25", "senha-errada"),  # CPF existe, senha errada
        ("111.444.777-35", SENHA),  # CPF que ninguém tem
        ("isto-nao-e-cpf", SENHA),  # nem chega a ser um CPF
    ]

    respostas = []
    for cpf, senha in tentativas:
        with pytest.raises(NaoAutenticado) as erro:
            service.autenticar(cpf, senha)
        respostas.append((erro.value.status_http, erro.value.codigo, erro.value.mensagem))

    assert respostas == [(401, "CREDENCIAIS_INVALIDAS", "CPF ou senha inválidos.")] * 3


def test_criar_credencial_recusa_cpf_repetido_e_nao_faz_commit():
    """RN-07: CPF repetido dá `CPF_JA_CADASTRADO`, sem inserir; quem chama é que faz o commit."""
    service = um_service()
    service.repository.buscar_por_cpf.return_value = um_usuario_gravado()

    with pytest.raises(ConflitoDeEstado) as erro:
        service.criar_credencial(
            "529.982.247-25", "Novo Eleitor", "Senha@2026", Perfil.ELEITOR, AGORA
        )

    assert erro.value.codigo == "CPF_JA_CADASTRADO"
    service.repository.inserir.assert_not_called()
    service.sessao.commit.assert_not_called()
