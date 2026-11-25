from app.core.database import SessionLocal
from app.services.usuario_service import UsuarioService
from tests.auxiliares import CPF_CHEFE, SENHA_CHEFE, criar_chefe, gerar_cpf


def _entrar(cliente, cpf, senha):
    return cliente.post("/api/v1/auth/login", data={"username": cpf, "password": senha})


def test_login_correto_devolve_token_e_perfil(cliente):
    """TI-01 / RN-01: CPF e senha certos devolvem o token e o perfil do usuário."""
    criar_chefe()

    resposta = _entrar(cliente, CPF_CHEFE, SENHA_CHEFE)

    corpo = resposta.json()
    assert resposta.status_code == 200
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["expira_em"]
    assert corpo["usuario"]["perfil"] == "CHEFE_SECAO"
    assert corpo["usuario"]["nome"] == "Chefe da Seção"


def test_login_aceita_cpf_com_pontuacao(cliente):
    """TI-01 / RN-01, RN-07: o CPF pode vir com ou sem pontuação."""
    criar_chefe()

    resposta = _entrar(cliente, "291.417.776-38", SENHA_CHEFE)

    assert resposta.status_code == 200


def test_login_com_senha_errada_responde_401(cliente):
    """TI-02 / RN-01: senha errada dá 401 CREDENCIAIS_INVALIDAS."""
    criar_chefe()

    resposta = _entrar(cliente, CPF_CHEFE, "Senha@Errada1")

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


def test_login_com_cpf_inexistente_responde_o_mesmo_401(cliente):
    """TI-03 / RN-01: CPF inexistente não se distingue de senha errada (mesma mensagem)."""
    criar_chefe()
    senha_errada = _entrar(cliente, CPF_CHEFE, "Senha@Errada1")

    cpf_inexistente = _entrar(cliente, gerar_cpf(7), SENHA_CHEFE)

    assert cpf_inexistente.status_code == 401
    assert cpf_inexistente.json() == senha_errada.json()


def test_login_com_cpf_mal_formatado_responde_o_mesmo_401(cliente):
    """TI-03 / RN-01: CPF fora do formato também não ajuda quem tenta adivinhar."""
    criar_chefe()
    senha_errada = _entrar(cliente, CPF_CHEFE, "Senha@Errada1")

    resposta = _entrar(cliente, "abc", SENHA_CHEFE)

    assert resposta.status_code == 401
    assert resposta.json() == senha_errada.json()


def test_login_com_cpf_de_digitos_de_outro_alfabeto_responde_o_mesmo_401(cliente):
    """TI-03 / RN-01, RN-07: dígitos arábico-índicos recebem o 401 genérico."""
    criar_chefe()
    senha_errada = _entrar(cliente, CPF_CHEFE, "Senha@Errada1")

    resposta = _entrar(cliente, "٢٩١٤١٧٧٧٦٣٨", SENHA_CHEFE)

    assert resposta.status_code == 401
    assert resposta.json() == senha_errada.json()


def test_rota_protegida_sem_token_responde_401_com_www_authenticate(cliente):
    """TI-04 / RN-06: sem token, 401 NAO_AUTENTICADO e o cabeçalho WWW-Authenticate."""
    resposta = cliente.get("/api/v1/auth/me")

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "NAO_AUTENTICADO"
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_responde_401(cliente):
    """TI-05 / RN-02: token que não é um JWT nosso dá 401 TOKEN_INVALIDO."""
    resposta = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer token-falso"})

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "TOKEN_INVALIDO"


def test_me_devolve_o_usuario_logado(cliente, cabecalho_chefe):
    """TI-06 / RN-02: /auth/me devolve os dados de quem está logado (sem senha nem hash)."""
    resposta = cliente.get("/api/v1/auth/me", headers=cabecalho_chefe)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": resposta.json()["id"],
        "nome": "Chefe da Seção",
        "cpf": CPF_CHEFE,
        "perfil": "CHEFE_SECAO",
    }


def test_usuario_excluido_perde_o_acesso_mesmo_com_token_valido(cliente):
    """TI-07 / RN-02: o usuário é recarregado do banco; excluído, o token antigo não vale."""
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
