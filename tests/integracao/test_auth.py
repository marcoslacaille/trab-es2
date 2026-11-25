from app.core.database import SessionLocal
from app.services.usuario_service import UsuarioService
from tests.auxiliares import CPF_CHEFE, SENHA_CHEFE, criar_chefe, gerar_cpf


def _entrar(cliente, cpf, senha):
    return cliente.post("/api/v1/auth/login", data={"username": cpf, "password": senha})


def test_login_devolve_token_e_perfil(cliente):
    """RN-01 e RN-07: CPF e senha certos devolvem o token e o perfil; o CPF pode ter pontuação."""
    criar_chefe()

    resposta = _entrar(cliente, CPF_CHEFE, SENHA_CHEFE)

    corpo = resposta.json()
    assert resposta.status_code == 200
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["expira_em"]
    assert corpo["usuario"]["perfil"] == "CHEFE_SECAO"
    assert corpo["usuario"]["nome"] == "Chefe da Seção"
    assert _entrar(cliente, "291.417.776-38", SENHA_CHEFE).status_code == 200


def test_login_invalido_responde_sempre_o_mesmo_401(cliente):
    """RN-01: senha errada, CPF inexistente e CPF mal formatado não se distinguem."""
    criar_chefe()
    senha_errada = _entrar(cliente, CPF_CHEFE, "Senha@Errada1")
    assert senha_errada.status_code == 401
    assert senha_errada.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"

    for cpf in (gerar_cpf(7), "abc"):
        resposta = _entrar(cliente, cpf, SENHA_CHEFE)

        assert resposta.status_code == 401, cpf
        assert resposta.json() == senha_errada.json(), cpf


def test_token_invalido_responde_401(cliente):
    """RN-02: token que não é um JWT nosso dá 401 TOKEN_INVALIDO."""
    resposta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer token-falso"})

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "TOKEN_INVALIDO"


def test_me_devolve_o_usuario_logado(cliente, cabecalho_chefe):
    """RN-02: /auth/me devolve os dados de quem está logado (sem senha nem hash)."""
    resposta = cliente.get("/api/v1/auth/me", headers=cabecalho_chefe)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": resposta.json()["id"],
        "nome": "Chefe da Seção",
        "cpf": CPF_CHEFE,
        "perfil": "CHEFE_SECAO",
    }


def test_usuario_excluido_perde_o_acesso_mesmo_com_token_valido(cliente):
    """RN-02: o usuário é recarregado do banco; excluído, o token antigo não vale."""
    usuario_id = criar_chefe()
    token = _entrar(cliente, CPF_CHEFE, SENHA_CHEFE).json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/api/v1/auth/me", headers=cabecalho).status_code == 200
    with SessionLocal() as sessao:
        UsuarioService(sessao).remover_credencial(usuario_id)
        sessao.commit()

    resposta = cliente.get("/api/v1/auth/me", headers=cabecalho)

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "TOKEN_INVALIDO"
