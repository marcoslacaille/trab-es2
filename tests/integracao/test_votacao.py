"""Cédula, registro e confirmação do voto pela API (RN-50 a RN-61)."""

from sqlalchemy import text

from app.core.database import SessionLocal
from tests.auxiliares import (
    SENHA_ELEITOR,
    eleicao_aberta_com_candidatos,
    login,
    nova_candidatura,
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


def test_cedula_lista_so_os_cargos_disputados_na_ordem_da_urna(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-55 e RN-61: só Senador e Presidente aparecem, nessa ordem, com `ja_votou`."""
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
    antes = cliente.get(f"{BASE}/{eleicao}/participacao", headers=cabecalho_eleitor)
    assert antes.json()["cargos"] == [
        {"cargo": "SENADOR", "ja_votou": False},
        {"cargo": "PRESIDENTE", "ja_votou": False},
    ]

    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "10").status_code == 201
    depois = cliente.get(f"{BASE}/{eleicao}/cedula", headers=cabecalho_eleitor).json()
    assert [c["ja_votou"] for c in depois["cargos"]] == [False, True]
    participacao = cliente.get(f"{BASE}/{eleicao}/participacao", headers=cabecalho_eleitor)
    assert participacao.status_code == 200
    assert participacao.json() == {
        "eleicao_id": eleicao,
        "cargos": [
            {"cargo": "SENADOR", "ja_votou": False},
            {"cargo": "PRESIDENTE", "ja_votou": True},
        ],
    }


def test_registrar_voto_devolve_a_previa_e_nao_grava_nada(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-56: prévia NOMINAL com candidato e token, sem gravar nada; quem muda de ideia confirma
    a nova cédula, e a anterior passa a dar 409."""
    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    eleicao = aberta["eleicao_id"]

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

    # Mudar de ideia: registra 20 e confirma; a primeira cédula, depois disso, dá 409.
    primeira = corpo["token_cedula"]
    segunda = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="20"
    ).json()["token_cedula"]
    assert _confirmar(cliente, cabecalho_eleitor, eleicao, segunda).status_code == 201

    reuso = _confirmar(cliente, cabecalho_eleitor, eleicao, primeira)

    assert reuso.status_code == 409
    assert _codigo(reuso) == "VOTO_JA_REGISTRADO"
    with SessionLocal() as sessao:
        votos = sessao.execute(text("SELECT candidatura_id FROM votos")).scalars().all()
    assert votos == [aberta["candidaturas"]["PRESIDENTE"]["20"]]


def test_numero_sem_candidatura_vira_nulo_e_modo_branco_vira_branco(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-58: número sem candidatura é NULO; modo BRANCO é BRANCO; o pedido segue o modo."""
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

    # O schema do pedido: número conforme o modo e conforme os dígitos do cargo.
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

    # Confirmados, NULO e BRANCO viram linhas em `votos` com candidatura nula.
    assert votar(cliente, cabecalho_eleitor, eleicao, "PRESIDENTE", "99").status_code == 201
    assert votar(cliente, cabecalho_eleitor, eleicao, "SENADOR", branco=True).status_code == 201
    with SessionLocal() as sessao:
        votos = sessao.execute(text("SELECT tipo, candidatura_id FROM votos ORDER BY tipo")).all()
    assert [(v.tipo, v.candidatura_id) for v in votos] == [("BRANCO", None), ("NULO", None)]


def test_confirmar_grava_uma_linha_em_cada_tabela_e_nao_devolve_a_escolha(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-56 e RN-60: a resposta não traz a escolha; 1 linha em `votos` e em registros."""
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


def test_um_voto_por_cargo(cliente, cabecalho_chefe, cabecalho_eleitor):
    """RN-54 e RN-59: não vota duas vezes no cargo, mas pode votar em outro cargo."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]
    assert _confirmar(cliente, cabecalho_eleitor, eleicao, token).status_code == 201

    segunda = _confirmar(cliente, cabecalho_eleitor, eleicao, token)
    novo_registro = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="20"
    )

    for resposta in (segunda, novo_registro):
        assert resposta.status_code == 409
        assert _codigo(resposta) == "VOTO_JA_REGISTRADO"
    assert _contar("votos") == 1

    outro_cargo = votar(cliente, cabecalho_eleitor, eleicao, "SENADOR", "101")  # um voto por cargo
    assert outro_cargo.status_code == 201
    assert _contar("registros_votacao") == 2


def test_voto_recusado_com_eleicao_fora_de_aberta_ou_da_janela(
    cliente, cabecalho_chefe, cabecalho_eleitor, relogio
):
    """RN-51 e RN-52: AGENDADA, ENCERRADA e depois das 17:00 recusam cédula, registro e voto."""
    agendada = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]

    cedula = cliente.get(f"{BASE}/{agendada}/cedula", headers=cabecalho_eleitor)
    registro = _registrar(cliente, cabecalho_eleitor, agendada, cargo="PRESIDENTE", modo="BRANCO")

    assert cedula.status_code == 409 and _codigo(cedula) == "ELEICAO_NAO_ABERTA"
    assert registro.status_code == 409 and _codigo(registro) == "ELEICAO_NAO_ABERTA"

    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    relogio.avancar(hours=6, minutes=58)  # 16:58: a cédula ainda valerá às 17:00
    token = _registrar(
        cliente, cabecalho_eleitor, aberta, cargo="PRESIDENTE", modo="BRANCO"
    ).json()["token_cedula"]

    relogio.avancar(minutes=2)  # 17:00, com a eleição ainda ABERTA
    cedula = cliente.get(f"{BASE}/{aberta}/cedula", headers=cabecalho_eleitor)
    registro = _registrar(cliente, cabecalho_eleitor, aberta, cargo="SENADOR", modo="BRANCO")
    confirmacao = _confirmar(cliente, cabecalho_eleitor, aberta, token)
    for resposta in (cedula, registro, confirmacao):
        assert resposta.status_code == 409
        assert _codigo(resposta) == "JANELA_ENCERRADA"

    encerra = cliente.post(f"/api/v1/eleicoes/{aberta}/encerramento", headers=cabecalho_chefe)
    assert encerra.status_code == 200
    na_encerrada = _confirmar(cliente, cabecalho_eleitor, aberta, token)
    assert na_encerrada.status_code == 409
    assert _codigo(na_encerrada) == "ELEICAO_NAO_ABERTA"
    assert _contar("votos") == 0


def test_cedula_de_outro_eleitor_ou_de_outra_eleicao_e_recusada(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-57: a cédula só vale para o eleitor e para a eleição de origem."""
    outro = _novo_eleitor_com_login(cliente, cabecalho_chefe)
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    outra_eleicao = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]

    de_outro_eleitor = _confirmar(cliente, outro, eleicao, token)
    de_outra_eleicao = _confirmar(cliente, cabecalho_eleitor, outra_eleicao, token)

    for resposta in (de_outro_eleitor, de_outra_eleicao):
        assert resposta.status_code == 422
        assert _codigo(resposta) == "CEDULA_INVALIDA"
    assert _contar("votos") == 0


def test_eleitor_cadastrado_depois_da_abertura_nao_e_apto(cliente, cabecalho_chefe, relogio):
    """RN-53: cadastrado depois da abertura, recebe 403 `ELEITOR_NAO_APTO`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    relogio.avancar(minutes=1)
    tardio = _novo_eleitor_com_login(cliente, cabecalho_chefe)

    cedula = cliente.get(f"{BASE}/{eleicao}/cedula", headers=tardio)
    registro = _registrar(cliente, tardio, eleicao, cargo="PRESIDENTE", modo="BRANCO")

    assert cedula.status_code == 403 and _codigo(cedula) == "ELEITOR_NAO_APTO"
    assert registro.status_code == 403 and _codigo(registro) == "ELEITOR_NAO_APTO"


def test_cedula_vencida_e_recusada_na_confirmacao(
    cliente, cabecalho_chefe, cabecalho_eleitor, relogio
):
    """RN-57: confirmada mais de 5 minutos depois do registro, a cédula dá 422 `CEDULA_EXPIRADA`."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    token = _registrar(
        cliente, cabecalho_eleitor, eleicao, cargo="PRESIDENTE", modo="NUMERO", numero="10"
    ).json()["token_cedula"]

    relogio.avancar(minutes=5, seconds=1)
    vencida = _confirmar(cliente, cabecalho_eleitor, eleicao, token)

    assert vencida.status_code == 422 and _codigo(vencida) == "CEDULA_EXPIRADA"
    assert _contar("votos") == 0


def test_mesmo_eleitor_vota_no_mesmo_cargo_em_cada_turno(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-54: o voto único é por eleição; no 2º turno o eleitor vota de novo no cargo, uma vez."""
    primeiro = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, cabecalho_eleitor, primeiro, "PRESIDENTE", "10").status_code == 201
    encerra = cliente.post(f"/api/v1/eleicoes/{primeiro}/encerramento", headers=cabecalho_chefe)
    assert encerra.status_code == 200

    segundo = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]
    for numero in ("10", "20"):
        assert nova_candidatura(cliente, cabecalho_chefe, segundo, numero=numero).status_code == 201
    abre = cliente.post(f"/api/v1/eleicoes/{segundo}/abertura", headers=cabecalho_chefe)
    assert abre.status_code == 200, abre.text

    no_segundo_turno = votar(cliente, cabecalho_eleitor, segundo, "PRESIDENTE", "20")
    de_novo = votar(cliente, cabecalho_eleitor, segundo, "PRESIDENTE", "10")

    assert no_segundo_turno.status_code == 201
    assert de_novo.status_code == 409 and _codigo(de_novo) == "VOTO_JA_REGISTRADO"
    assert _contar("registros_votacao") == 2
