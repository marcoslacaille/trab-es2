"""TI-38 a TI-54: cédula, registro e confirmação do voto pela API (RN-50 a RN-61)."""

from sqlalchemy import text

from app.compartilhado.banco import SessionLocal
from tests.auxiliares import (
    SENHA_ELEITOR,
    eleicao_aberta_com_candidatos,
    login,
    nova_eleicao,
    novo_eleitor,
    votar,
)

BASE = "/api/v1/votacao/eleicoes"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def _registrar(cliente, cabecalho, eleicao_id, **pedido):
    return cliente.post(f"{BASE}/{eleicao_id}/votos/registro", json=pedido, headers=cabecalho)


def _confirmar(cliente, cabecalho, eleicao_id, token):
    return cliente.post(
        f"{BASE}/{eleicao_id}/votos/confirmacao", json={"token_cedula": token}, headers=cabecalho
    )


def _contar(tabela: str) -> int:
    with SessionLocal() as sessao:
        return sessao.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar_one()


def _novo_eleitor_com_login(cliente, cabecalho_chefe) -> dict[str, str]:
    resposta = novo_eleitor(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_ELEITOR)


def test_ti38_cedula_lista_so_cargos_disputados_na_ordem_da_urna(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-38 / RN-55, RN-61: só Senador e Presidente aparecem, nessa ordem, com ja_votou."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    resposta = cliente.get(f"{BASE}/{eleicao}/cedula", headers=cabecalho_eleitor)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["eleicao_id"] == eleicao
    assert [c["cargo"] for c in corpo["cargos"]] == ["SENADOR", "PRESIDENTE"]
    senador, presidente = corpo["cargos"]
    assert senador["digitos"] == 3 and presidente["digitos"] == 2
    assert not senador["ja_votou"] and not presidente["ja_votou"]
    assert [c["numero"] for c in presidente["candidatos"]] == ["10", "20"]
    assert set(presidente["candidatos"][0]) == {"numero", "nome_urna", "partido_sigla"}

    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201
    depois = cliente.get(f"{BASE}/{eleicao}/cedula", headers=cabecalho_eleitor).json()
    assert [c["ja_votou"] for c in depois["cargos"]] == [False, True]


def test_ti38_cedula_de_eleicao_inexistente_da_404(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-38 / RN-50: eleição inexistente dá 404 `ELEICAO_NAO_ENCONTRADA`."""
    resposta = cliente.get(f"{BASE}/99/cedula", headers=cabecalho_eleitor)

    assert resposta.status_code == 404
    assert _codigo(resposta) == "ELEICAO_NAO_ENCONTRADA"


def test_ti39_registrar_voto_nominal_devolve_previa_e_nao_grava_nada(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-39 / RN-56: prévia NOMINAL com candidato e token; `votos` e `registros_votacao` vazios."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    resposta = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["cargo"] == "PRESIDENTE"
    assert corpo["tipo_voto"] == "NOMINAL"
    assert corpo["candidato"]["numero"] == "10"
    assert corpo["token_cedula"]
    assert corpo["expira_em"].startswith("2026-11-25T10:05:00")
    assert corpo["links"] == [
        {"rel": "confirmar", "metodo": "POST", "href": f"{BASE}/{eleicao}/votos/confirmacao"}
    ]
    assert _contar("votos") == 0
    assert _contar("registros_votacao") == 0


def test_ti39_registro_recusa_numero_conforme_o_modo(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-39 / RN-58: sem número no modo NUMERO, número no BRANCO e número com letra dão 422."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    sem_numero = _registrar(cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO")
    branco_com_numero = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="BRANCO", numero="10"
    )
    com_letra = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="1a"
    )
    campo_extra = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="BRANCO", branco=True
    )
    digitos_errados = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="101"
    )

    assert [r.status_code for r in (sem_numero, branco_com_numero, com_letra, campo_extra)] == [
        422
    ] * 4
    assert digitos_errados.status_code == 422
    assert _codigo(digitos_errados) == "NUMERO_INVALIDO_PARA_CARGO"


def test_ti40_numero_inexistente_vira_nulo_e_modo_branco_vira_branco(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-40 / RN-58: número sem candidatura é NULO; modo BRANCO é BRANCO."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    nulo = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="99"
    )
    branco = _registrar(cliente, cabecalho_eleitor, eleicao, cargo="SENADOR", modo="BRANCO")

    assert nulo.status_code == 200
    assert nulo.json()["tipo_voto"] == "NULO"
    assert nulo.json()["candidato"] is None
    assert "NULO" in nulo.json()["mensagem"]
    assert branco.status_code == 200
    assert branco.json()["tipo_voto"] == "BRANCO"
    assert branco.json()["candidato"] is None


def test_ti41_confirmar_devolve_201_sem_a_escolha_e_grava_uma_linha_em_cada_tabela(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-41 / RN-56, RN-60: a resposta não traz a escolha; 1 linha em `votos` e em registros."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    resposta = votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10")

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"eleicao_id", "cargo", "mensagem", "links"}
    assert corpo["mensagem"] == "Voto confirmado."
    assert [link["rel"] for link in corpo["links"]] == ["cedula", "participacao"]
    assert _contar("votos") == 1
    assert _contar("registros_votacao") == 1
    with SessionLocal() as sessao:
        voto = sessao.execute(text("SELECT cargo, tipo, candidatura_id FROM votos")).one()
    assert (voto.cargo, voto.tipo, voto.candidatura_id) == ("PRESIDENTE", "NOMINAL", 1)


def test_ti41_votos_nulo_e_branco_sao_gravados_sem_candidatura(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-41 / RN-58: NULO e BRANCO viram linhas em `votos` com candidatura nula."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "99").status_code == 201
    assert votar(cliente, cabecalho_eleitor, eleicao, "SENADOR", branco=True).status_code == 201

    with SessionLocal() as sessao:
        votos = sessao.execute(text("SELECT tipo, candidatura_id FROM votos ORDER BY tipo")).all()
    assert [(v.tipo, v.candidatura_id) for v in votos] == [("BRANCO", None), ("NULO", None)]


def test_ti42_confirmar_a_mesma_cedula_de_novo_da_409(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-42 / RN-54, RN-59: a segunda confirmação dá 409 `VOTO_JA_REGISTRADO`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]
    assert _confirmar(cliente, cabecalho_eleitor, eleicao, token).status_code == 201

    segunda = _confirmar(cliente, cabecalho_eleitor, eleicao, token)

    assert segunda.status_code == 409
    assert _codigo(segunda) == "VOTO_JA_REGISTRADO"
    assert _contar("votos") == 1


def test_ti43_registrar_de_novo_no_mesmo_cargo_depois_de_confirmar_da_409(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-43 / RN-54: já votou em Presidente, então o registro em Presidente dá 409."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201

    resposta = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="20"
    )

    assert resposta.status_code == 409
    assert _codigo(resposta) == "VOTO_JA_REGISTRADO"


def test_ti44_votar_em_outro_cargo_depois_do_primeiro_funciona(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-44 / RN-54: o limite é um voto por cargo, não um voto por eleição."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201

    resposta = votar(cliente, cabecalho_eleitor, eleicao, "SENADOR", "101")

    assert resposta.status_code == 201
    assert _contar("registros_votacao") == 2


def test_ti45_eleicao_agendada_ou_encerrada_da_409(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-45 / RN-51: AGENDADA e ENCERRADA recusam cédula e registro com `ELEICAO_NAO_ABERTA`."""
    agendada = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]

    cedula = cliente.get(f"{BASE}/{agendada}/cedula", headers=cabecalho_eleitor)
    registro = _registrar(cliente, cabecalho_eleitor, agendada, cargo="PRESIDENTE", modo="BRANCO")

    assert cedula.status_code == 409 and _codigo(cedula) == "ELEICAO_NAO_ABERTA"
    assert registro.status_code == 409 and _codigo(registro) == "ELEICAO_NAO_ABERTA"

    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, aberta, cargo="PRESIDENTE", modo="BRANCO"
    ).json()["token_cedula"]
    encerra = cliente.post(f"/api/v1/eleicoes/{aberta}/encerramento", headers=cabecalho_chefe)
    assert encerra.status_code == 200

    na_encerrada = _confirmar(cliente, cabecalho_eleitor, aberta, token)
    assert na_encerrada.status_code == 409
    assert _codigo(na_encerrada) == "ELEICAO_NAO_ABERTA"
    assert _contar("votos") == 0


def test_ti46_chefe_e_candidato_nao_votam(
    cliente, cabecalho_chefe, cabecalho_candidato, cabecalho_eleitor
):
    """TI-46 / RN-50: Chefe e Candidato recebem 403 `PERFIL_NAO_AUTORIZADO` nas 4 rotas."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    for cabecalho in (cabecalho_chefe, cabecalho_candidato):
        respostas = [
            cliente.get(f"{BASE}/{eleicao}/cedula", headers=cabecalho),
            _registrar(cliente, cabecalho, eleicao, cargo="PRESIDENTE", modo="BRANCO"),
            _confirmar(cliente, cabecalho, eleicao, "qualquer"),
            cliente.get(f"{BASE}/{eleicao}/participacao", headers=cabecalho),
        ]
        for resposta in respostas:
            assert resposta.status_code == 403
            assert _codigo(resposta) == "PERFIL_NAO_AUTORIZADO"


def test_ti46_sem_login_da_401(cliente):
    """TI-46 / RN-50: sem token, 401."""
    assert cliente.get(f"{BASE}/1/cedula").status_code == 401


def test_ti47_cedula_de_outro_eleitor_da_422(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-47 / RN-57: a cédula de um eleitor não vale para outro."""
    outro = _novo_eleitor_com_login(cliente, cabecalho_chefe)
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]

    resposta = _confirmar(cliente, outro, eleicao, token)

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CEDULA_INVALIDA"
    assert _contar("votos") == 0


def test_ti47_texto_qualquer_no_lugar_da_cedula_da_422(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-47 / RN-57: token adulterado dá `CEDULA_INVALIDA`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    resposta = _confirmar(cliente, cabecalho_eleitor, eleicao, "isto-nao-e-uma-cedula")

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CEDULA_INVALIDA"


def test_ti48_cedula_de_outra_eleicao_da_422(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-48 / RN-57: cédula emitida na eleição 1 não vale na eleição 2."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    outra = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]

    resposta = _confirmar(cliente, cabecalho_eleitor, outra, token)

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CEDULA_INVALIDA"


def test_ti49_cedula_expira_em_5_minutos(cliente, cabecalho_chefe, cabecalho_eleitor, relogio):
    """TI-49 / RN-57: depois de 6 minutos, confirmar dá 422 `CEDULA_EXPIRADA`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]

    relogio.avancar(minutes=6)
    resposta = _confirmar(cliente, cabecalho_eleitor, eleicao, token)

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CEDULA_EXPIRADA"
    assert _contar("votos") == 0


def test_ti50_eleitor_cadastrado_depois_da_abertura_nao_e_apto(cliente, cabecalho_chefe, relogio):
    """TI-50 / RN-53: cadastrado depois da abertura, recebe 403 `ELEITOR_NAO_APTO`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    relogio.avancar(minutes=1)
    tardio = _novo_eleitor_com_login(cliente, cabecalho_chefe)

    cedula = cliente.get(f"{BASE}/{eleicao}/cedula", headers=tardio)
    registro = _registrar(cliente, tardio, eleicao, cargo="PRESIDENTE", modo="BRANCO")

    assert cedula.status_code == 403 and _codigo(cedula) == "ELEITOR_NAO_APTO"
    assert registro.status_code == 403 and _codigo(registro) == "ELEITOR_NAO_APTO"


def test_ti51_cargo_sem_candidaturas_da_422(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-51 / RN-55: Governador não tem candidatura nesta eleição."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]

    resposta = _registrar(cliente, cabecalho_eleitor, eleicao, cargo="GOVERNADOR", modo="BRANCO")

    assert resposta.status_code == 422
    assert _codigo(resposta) == "CARGO_NAO_DISPUTADO"


def test_ti52_depois_do_horario_de_encerramento_da_409(
    cliente, cabecalho_chefe, cabecalho_eleitor, relogio
):
    """TI-52 / RN-52: às 17:00 em ponto o voto é recusado, mesmo com a eleição ABERTA."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    relogio.avancar(hours=6, minutes=58)  # 16:58: a cédula ainda valerá às 17:00
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="BRANCO"
    ).json()["token_cedula"]

    relogio.avancar(minutes=2)  # 17:00
    cedula = cliente.get(f"{BASE}/{eleicao}/cedula", headers=cabecalho_eleitor)
    registro = _registrar(cliente, cabecalho_eleitor, eleicao, cargo="SENADOR", modo="BRANCO")
    confirmacao = _confirmar(cliente, cabecalho_eleitor, eleicao, token)

    for resposta in (cedula, registro, confirmacao):
        assert resposta.status_code == 409
        assert _codigo(resposta) == "JANELA_ENCERRADA"
    assert _contar("votos") == 0


def test_ti53_participacao_mostra_cargos_votados_sem_a_escolha(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-53 / RN-61: `ja_votou` por cargo disputado e nenhuma informação sobre a escolha."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    antes = cliente.get(f"{BASE}/{eleicao}/participacao", headers=cabecalho_eleitor)
    assert antes.json()["cargos"] == [
        {"cargo": "SENADOR", "ja_votou": False},
        {"cargo": "PRESIDENTE", "ja_votou": False},
    ]

    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "20").status_code == 201
    depois = cliente.get(f"{BASE}/{eleicao}/participacao", headers=cabecalho_eleitor)

    assert depois.status_code == 200
    assert depois.json() == {
        "eleicao_id": eleicao,
        "cargos": [
            {"cargo": "SENADOR", "ja_votou": False},
            {"cargo": "PRESIDENTE", "ja_votou": True},
        ],
    }


def test_ti53_participacao_de_eleicao_inexistente_da_404(cliente, cabecalho_eleitor):
    """TI-53 / RN-61: eleição inexistente dá 404."""
    resposta = cliente.get(f"{BASE}/99/participacao", headers=cabecalho_eleitor)

    assert resposta.status_code == 404
    assert _codigo(resposta) == "ELEICAO_NAO_ENCONTRADA"


def test_ti54_mudar_de_ideia_vale_a_ultima_cedula_confirmada(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """TI-54 / RN-56: registra 10, registra 20, confirma a 2ª; a 1ª depois disso dá 409."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    id_eleicao = eleicao["eleicao_id"]
    primeira = _registrar(
        cliente, cabecalho_eleitor, id_eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]
    segunda = _registrar(
        cliente, cabecalho_eleitor, id_eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="20"
    ).json()["token_cedula"]

    assert _confirmar(cliente, cabecalho_eleitor, id_eleicao, segunda).status_code == 201
    reuso = _confirmar(cliente, cabecalho_eleitor, id_eleicao, primeira)

    assert reuso.status_code == 409
    assert _codigo(reuso) == "VOTO_JA_REGISTRADO"
    with SessionLocal() as sessao:
        votos = sessao.execute(text("SELECT candidatura_id FROM votos")).scalars().all()
    assert votos == [eleicao["candidaturas"]["PRESIDENTE"]["20"]]
