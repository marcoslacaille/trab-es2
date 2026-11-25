"""Apuração parcial e resultado final pela API (RN-70 a RN-79)."""

from tests.auxiliares import (
    SENHA_CANDIDATO,
    SENHA_ELEITOR,
    eleicao_aberta_com_candidatos,
    login,
    nova_candidatura,
    nova_eleicao,
    novo_candidato,
    novo_eleitor,
    novo_partido,
    votar,
)

BASE = "/api/v1/apuracao/eleicoes"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def _novo_eleitor_com_login(cliente, cabecalho_chefe) -> dict[str, str]:
    resposta = novo_eleitor(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_ELEITOR)


def _montar_eleicao(cliente, cabecalho_chefe, candidatos: list[tuple[str, str, str]]):
    """Cria a eleição com um candidato novo por `(cargo, numero, nascimento)` e a abre.

    Devolve `(eleicao_id, {numero: cabecalho_de_login_do_candidato})`.
    """
    eleicao = nova_eleicao(cliente, cabecalho_chefe).json()["id"]
    partido = novo_partido(cliente, cabecalho_chefe).json()["id"]
    logins = {}
    for cargo, numero, nascimento in candidatos:
        candidato = novo_candidato(cliente, cabecalho_chefe, data_nascimento=nascimento)
        assert candidato.status_code == 201, candidato.text
        candidatura = nova_candidatura(
            cliente,
            cabecalho_chefe,
            eleicao,
            candidato_id=candidato.json()["id"],
            partido_id=partido,
            cargo=cargo,
            numero=numero,
        )
        assert candidatura.status_code == 201, candidatura.text
        logins[numero] = login(cliente, candidato.json()["cpf"], SENHA_CANDIDATO)
    abertura = cliente.post(f"/api/v1/eleicoes/{eleicao}/abertura", headers=cabecalho_chefe)
    assert abertura.status_code == 200, abertura.text
    return eleicao, logins


def _encerrar(cliente, cabecalho_chefe, eleicao_id: int) -> None:
    resposta = cliente.post(f"/api/v1/eleicoes/{eleicao_id}/encerramento", headers=cabecalho_chefe)
    assert resposta.status_code == 200, resposta.text


def _cargo(corpo: dict, nome: str) -> dict:
    return next(c for c in corpo["cargos"] if c["cargo"] == nome)


def _votos(cargo: dict) -> dict[str, int]:
    return {c["numero"]: c["votos"] for c in cargo["candidatos"]}


def _novo_candidato_logado(cliente, cabecalho_chefe) -> dict[str, str]:
    resposta = novo_candidato(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_CANDIDATO)


def _candidato_da_candidatura(cliente, cabecalho_chefe, eleicao_id: int, numero: str) -> int:
    resposta = cliente.get(f"/api/v1/eleicoes/{eleicao_id}/candidaturas", headers=cabecalho_chefe)
    assert resposta.status_code == 200, resposta.text
    return next(c["candidato"]["id"] for c in resposta.json() if c["numero"] == numero)


def test_parcial_muda_a_cada_voto_confirmado(cliente, cabecalho_chefe):
    """RN-74: a parcial é recalculada a cada consulta (0 → 1 → 2 votos)."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    eleitor_1 = _novo_eleitor_com_login(cliente, cabecalho_chefe)
    eleitor_2 = _novo_eleitor_com_login(cliente, cabecalho_chefe)

    def total() -> int:
        r = cliente.get(f"{BASE}/{eleicao}/parcial?cargo=PRESIDENTE", headers=eleitor_1)
        assert r.status_code == 200, r.text
        return _cargo(r.json(), "PRESIDENTE")["total_votos"]

    assert total() == 0
    assert votar(cliente, eleitor_1, eleicao, "PRESIDENTE", "10").status_code == 201
    assert total() == 1
    assert votar(cliente, eleitor_2, eleicao, "PRESIDENTE", "20").status_code == 201
    assert total() == 2


def test_apuracao_fora_do_status_certo_responde_409(cliente, cabecalho_chefe):
    """RN-70: parcial só com eleição ABERTA e resultado final só com ENCERRADA."""
    agendada = nova_eleicao(cliente, cabecalho_chefe, data="2026-12-25").json()["id"]
    resposta = cliente.get(f"{BASE}/{agendada}/parcial", headers=cabecalho_chefe)
    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    assert resposta.json()["erro"]["detalhes"]["status"] == "AGENDADA"

    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    resposta = cliente.get(f"{BASE}/{aberta}/resultado", headers=cabecalho_chefe)
    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    assert resposta.json()["erro"]["detalhes"]["status"] == "ABERTA"
    assert cliente.get(f"{BASE}/999/resultado", headers=cabecalho_chefe).status_code == 404

    _encerrar(cliente, cabecalho_chefe, aberta)
    resposta = cliente.get(f"{BASE}/{aberta}/parcial", headers=cabecalho_chefe)
    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    detalhes = resposta.json()["erro"]["detalhes"]
    assert detalhes["status"] == "ENCERRADA"
    assert detalhes["resultado"] == f"/api/v1/apuracao/eleicoes/{aberta}/resultado"


def test_candidato_ve_so_o_cargo_da_sua_candidatura(cliente, cabecalho_chefe):
    """RN-72: só o próprio cargo; outro cargo ou sem candidatura → 403."""
    eleicao, candidatos = _montar_eleicao(
        cliente,
        cabecalho_chefe,
        [("PRESIDENTE", "10", "1960-01-01"), ("SENADOR", "101", "1970-01-01")],
    )
    do_presidente = candidatos["10"]

    proprio = cliente.get(f"{BASE}/{eleicao}/parcial", headers=do_presidente)
    assert proprio.status_code == 200, proprio.text
    assert [c["cargo"] for c in proprio.json()["cargos"]] == ["PRESIDENTE"]
    com_cargo = cliente.get(f"{BASE}/{eleicao}/parcial?cargo=PRESIDENTE", headers=do_presidente)
    assert com_cargo.status_code == 200

    outro = cliente.get(f"{BASE}/{eleicao}/parcial?cargo=SENADOR", headers=do_presidente)
    assert outro.status_code == 403
    assert _codigo(outro) == "CARGO_NAO_PERMITIDO"

    de_fora = _novo_candidato_logado(cliente, cabecalho_chefe)
    barrado = cliente.get(f"{BASE}/{eleicao}/parcial", headers=de_fora)
    assert barrado.status_code == 403
    assert _codigo(barrado) == "SEM_CANDIDATURA_NA_ELEICAO"


def test_eleitor_e_chefe_veem_todos_os_cargos(cliente, cabecalho_chefe):
    """RN-71: Eleitor e Chefe veem a parcial de todos os cargos."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    eleitor = _novo_eleitor_com_login(cliente, cabecalho_chefe)

    for cabecalho in (eleitor, cabecalho_chefe):
        resposta = cliente.get(f"{BASE}/{eleicao}/parcial", headers=cabecalho)
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["tipo"] == "PARCIAL"
        assert corpo["status_eleicao"] == "ABERTA"
        assert [c["cargo"] for c in corpo["cargos"]] == ["SENADOR", "PRESIDENTE"]
        assert all(
            "data_nascimento" not in c for cargo in corpo["cargos"] for c in cargo["candidatos"]
        )

    so_senador = cliente.get(f"{BASE}/{eleicao}/parcial?cargo=SENADOR", headers=eleitor)
    assert [c["cargo"] for c in so_senador.json()["cargos"]] == ["SENADOR"]
    nao_disputado = cliente.get(f"{BASE}/{eleicao}/parcial?cargo=GOVERNADOR", headers=eleitor)
    assert nao_disputado.status_code == 422
    assert _codigo(nao_disputado) == "CARGO_NAO_DISPUTADO"
    assert cliente.get(f"{BASE}/{eleicao}/parcial?cargo=XYZ", headers=eleitor).status_code == 422
    assert cliente.get(f"{BASE}/999/parcial", headers=eleitor).status_code == 404
    assert cliente.get(f"{BASE}/{eleicao}/parcial").status_code == 401


def test_resultado_final_traz_votos_percentuais_e_o_mais_votado(cliente, cabecalho_chefe, relogio):
    """RN-73 a 76 e 79: votos, percentuais, brancos, nulos, mais votado e comparecimento.

    Há 5 eleitores aptos (cadastrados antes da abertura) e 4 votantes. Um 6º eleitor é
    cadastrado depois da abertura, com o relógio já adiantado: ele não entra nos aptos (RN-53),
    e a conta continua 5 aptos, 4 votantes e 1 abstenção.
    """
    eleitores = [_novo_eleitor_com_login(cliente, cabecalho_chefe) for _ in range(5)]
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    relogio.avancar(minutes=1)
    _novo_eleitor_com_login(cliente, cabecalho_chefe)  # cadastrado depois da abertura
    for eleitor, numero in zip(eleitores[:3], ["10", "10", "20"], strict=True):
        assert votar(cliente, eleitor, eleicao, "PRESIDENTE", numero).status_code == 201
    assert votar(cliente, eleitores[3], eleicao, "PRESIDENTE", branco=True).status_code == 201
    assert votar(cliente, eleitores[0], eleicao, "SENADOR", "999").status_code == 201  # nulo
    comparecimento = {"eleitores_aptos": 5, "votantes": 4, "abstencao": 1}
    parcial = cliente.get(f"{BASE}/{eleicao}/parcial", headers=cabecalho_chefe).json()
    assert parcial["comparecimento"] == comparecimento
    _encerrar(cliente, cabecalho_chefe, eleicao)

    for cabecalho in (cabecalho_chefe, eleitores[0]):
        resposta = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho)
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["tipo"] == "FINAL"
        assert corpo["status_eleicao"] == "ENCERRADA"
        assert corpo["comparecimento"] == comparecimento

        presidente = _cargo(corpo, "PRESIDENTE")
        assert (presidente["total_votos"], presidente["votos_validos"]) == (4, 3)
        assert (presidente["brancos"], presidente["nulos"]) == (1, 0)
        assert presidente["situacao"] == "DEFINIDO"
        assert presidente["criterio"] == "MAIOR_VOTACAO"
        assert presidente["mais_votado"]["numero"] == "10"
        linhas = [
            (c["numero"], c["votos"], c["percentual_validos"]) for c in presidente["candidatos"]
        ]
        assert linhas == [("10", 2, "66.67"), ("20", 1, "33.33")]

        senador = _cargo(corpo, "SENADOR")
        assert senador["total_votos"] == 1
        assert senador["nulos"] == 1 and senador["votos_validos"] == 0
        assert senador["situacao"] == "SEM_VOTOS_VALIDOS"
        assert senador["mais_votado"] is None
        assert _votos(senador) == {"101": 0, "202": 0}

    candidato = _novo_candidato_logado(cliente, cabecalho_chefe)
    assert cliente.get(f"{BASE}/{eleicao}/resultado", headers=candidato).status_code == 200


def test_desempate_usa_a_data_de_nascimento_gravada_na_abertura(cliente, cabecalho_chefe):
    """RN-75 e RN-77: o empate vai para o mais idoso, com os dados gravados na abertura.

    Depois da abertura, editar a data de nascimento ou o nome de urna do candidato não muda a
    apuração: sem isso, deixar o candidato 20 "mais velho" depois do fim trocava o mais votado.
    A edição continua valendo para o candidato e para as eleições ainda AGENDADAS.
    """
    eleicao, _ = _montar_eleicao(
        cliente,
        cabecalho_chefe,
        [("PRESIDENTE", "10", "1950-01-01"), ("PRESIDENTE", "20", "1980-01-01")],
    )
    eleitor_1 = _novo_eleitor_com_login(cliente, cabecalho_chefe)
    eleitor_2 = _novo_eleitor_com_login(cliente, cabecalho_chefe)
    assert votar(cliente, eleitor_1, eleicao, "PRESIDENTE", "10").status_code == 201
    assert votar(cliente, eleitor_2, eleicao, "PRESIDENTE", "20").status_code == 201
    candidato_10 = _candidato_da_candidatura(cliente, cabecalho_chefe, eleicao, "10")
    candidato_20 = _candidato_da_candidatura(cliente, cabecalho_chefe, eleicao, "20")
    nome_da_abertura = cliente.get(f"/api/v1/candidatos/{candidato_10}", headers=cabecalho_chefe)
    nome_da_abertura = nome_da_abertura.json()["nome_urna"]

    agendada = nova_eleicao(cliente, cabecalho_chefe, data="2026-11-26").json()["id"]
    nova = nova_candidatura(cliente, cabecalho_chefe, agendada, candidato_id=candidato_10)
    assert nova.status_code == 201, nova.text
    edicao = cliente.patch(
        f"/api/v1/candidatos/{candidato_10}",
        json={"nome_urna": "Nome Novo"},
        headers=cabecalho_chefe,
    )
    assert edicao.status_code == 200, edicao.text
    cedula = cliente.get(f"/api/v1/votacao/eleicoes/{eleicao}/cedula", headers=eleitor_1).json()
    assert cedula["cargos"][0]["candidatos"][0]["nome_urna"] == nome_da_abertura
    parcial = cliente.get(f"{BASE}/{eleicao}/parcial", headers=cabecalho_chefe).json()
    assert _cargo(parcial, "PRESIDENTE")["candidatos"][0]["nome_urna"] == nome_da_abertura
    da_agendada = cliente.get(
        f"/api/v1/eleicoes/{agendada}/candidaturas", headers=cabecalho_chefe
    ).json()
    assert da_agendada[0]["candidato"]["nome_urna"] == "Nome Novo"

    _encerrar(cliente, cabecalho_chefe, eleicao)
    corpo = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho_chefe).json()
    presidente = _cargo(corpo, "PRESIDENTE")
    assert presidente["situacao"] == "DEFINIDO"
    assert presidente["criterio"] == "DESEMPATE_POR_IDADE"
    assert presidente["mais_votado"]["numero"] == "10"
    assert _votos(presidente) == {"10": 1, "20": 1}
    assert presidente["candidatos"][0]["nome_urna"] == nome_da_abertura

    edicao = cliente.patch(
        f"/api/v1/candidatos/{candidato_20}",
        json={"data_nascimento": "1940-01-01"},
        headers=cabecalho_chefe,
    )
    assert edicao.status_code == 200, edicao.text
    depois = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho_chefe).json()
    presidente = _cargo(depois, "PRESIDENTE")
    assert presidente["criterio"] == "DESEMPATE_POR_IDADE"
    assert presidente["mais_votado"]["numero"] == "10"
