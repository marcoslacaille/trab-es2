"""TI-55 a TI-62: apuração parcial e resultado final pela API (RN-70 a RN-79)."""

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


def test_ti55_parcial_muda_a_cada_voto_confirmado(cliente, cabecalho_chefe):
    """TI-55 / RN-74: a parcial é recalculada a cada consulta (0 → 1 → 2 votos)."""
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


def test_ti56_parcial_com_eleicao_agendada_ou_encerrada_da_409(cliente, cabecalho_chefe):
    """TI-56 / RN-70: parcial só com eleição ABERTA."""
    agendada = nova_eleicao(cliente, cabecalho_chefe, data="2026-12-25").json()["id"]
    resposta = cliente.get(f"{BASE}/{agendada}/parcial", headers=cabecalho_chefe)
    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    assert resposta.json()["erro"]["detalhes"]["status"] == "AGENDADA"

    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    _encerrar(cliente, cabecalho_chefe, aberta)
    resposta = cliente.get(f"{BASE}/{aberta}/parcial", headers=cabecalho_chefe)
    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    detalhes = resposta.json()["erro"]["detalhes"]
    assert detalhes["status"] == "ENCERRADA"
    assert detalhes["resultado"] == f"/api/v1/apuracao/eleicoes/{aberta}/resultado"


def test_ti57_candidato_ve_so_o_seu_cargo(cliente, cabecalho_chefe):
    """TI-57 / RN-72: só o próprio cargo; outro cargo ou sem candidatura → 403."""
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


def test_ti58_eleitor_e_chefe_veem_todos_os_cargos(cliente, cabecalho_chefe):
    """TI-58 / RN-71: Eleitor e Chefe veem a parcial de todos os cargos."""
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


def test_ti59_resultado_com_eleicao_aberta_da_409(cliente, cabecalho_chefe):
    """TI-59 / RN-70: resultado final só com eleição ENCERRADA."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    resposta = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert _codigo(resposta) == "APURACAO_INDISPONIVEL"
    assert resposta.json()["erro"]["detalhes"]["status"] == "ABERTA"
    assert cliente.get(f"{BASE}/999/resultado", headers=cabecalho_chefe).status_code == 404


def test_ti60_resultado_final_com_votos_percentuais_e_mais_votado(cliente, cabecalho_chefe):
    """TI-60 / RN-73 a 76: votos, percentuais, brancos, nulos e mais votado por cargo."""
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    eleitores = [_novo_eleitor_com_login(cliente, cabecalho_chefe) for _ in range(4)]
    for eleitor, numero in zip(eleitores[:3], ["10", "10", "20"], strict=True):
        assert votar(cliente, eleitor, eleicao, "PRESIDENTE", numero).status_code == 201
    assert votar(cliente, eleitores[3], eleicao, "PRESIDENTE", branco=True).status_code == 201
    assert votar(cliente, eleitores[0], eleicao, "SENADOR", "999").status_code == 201  # nulo
    _encerrar(cliente, cabecalho_chefe, eleicao)

    for cabecalho in (cabecalho_chefe, eleitores[0]):
        resposta = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho)
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["tipo"] == "FINAL"
        assert corpo["status_eleicao"] == "ENCERRADA"

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
        assert senador["nulos"] == 1 and senador["votos_validos"] == 0
        assert senador["situacao"] == "SEM_VOTOS_VALIDOS"
        assert senador["mais_votado"] is None
        assert _votos(senador) == {"101": 0, "202": 0}

    candidato = _novo_candidato_logado(cliente, cabecalho_chefe)
    assert cliente.get(f"{BASE}/{eleicao}/resultado", headers=candidato).status_code == 200


def test_ti61_empate_no_resultado_e_decidido_pelo_mais_idoso(cliente, cabecalho_chefe):
    """TI-61 / RN-77: mesmo número de votos → vence o mais idoso (DESEMPATE_POR_IDADE)."""
    eleicao, _ = _montar_eleicao(
        cliente,
        cabecalho_chefe,
        [("PRESIDENTE", "10", "1980-06-01"), ("PRESIDENTE", "20", "1955-02-10")],
    )
    eleitores = [_novo_eleitor_com_login(cliente, cabecalho_chefe) for _ in range(2)]
    assert votar(cliente, eleitores[0], eleicao, "PRESIDENTE", "10").status_code == 201
    assert votar(cliente, eleitores[1], eleicao, "PRESIDENTE", "20").status_code == 201
    _encerrar(cliente, cabecalho_chefe, eleicao)

    corpo = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho_chefe).json()
    presidente = _cargo(corpo, "PRESIDENTE")
    assert presidente["situacao"] == "DEFINIDO"
    assert presidente["criterio"] == "DESEMPATE_POR_IDADE"
    assert presidente["mais_votado"]["numero"] == "20"
    assert _votos(presidente) == {"10": 1, "20": 1}


def test_ti62_comparecimento_aptos_votantes_e_abstencao(cliente, cabecalho_chefe):
    """TI-62 / RN-79: aptos (cadastrados antes da abertura), votantes e abstenção."""
    eleitores = [_novo_eleitor_com_login(cliente, cabecalho_chefe) for _ in range(3)]
    eleicao = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)["eleicao_id"]
    assert votar(cliente, eleitores[0], eleicao, "PRESIDENTE", "10").status_code == 201
    assert votar(cliente, eleitores[0], eleicao, "SENADOR", "101").status_code == 201
    assert votar(cliente, eleitores[1], eleicao, "PRESIDENTE", branco=True).status_code == 201

    parcial = cliente.get(f"{BASE}/{eleicao}/parcial", headers=cabecalho_chefe).json()
    assert parcial["comparecimento"] == {"eleitores_aptos": 3, "votantes": 2, "abstencao": 1}

    _encerrar(cliente, cabecalho_chefe, eleicao)
    final = cliente.get(f"{BASE}/{eleicao}/resultado", headers=cabecalho_chefe).json()
    assert final["comparecimento"] == {"eleitores_aptos": 3, "votantes": 2, "abstencao": 1}
    assert _cargo(final, "PRESIDENTE")["total_votos"] == 2
    assert _cargo(final, "SENADOR")["total_votos"] == 1


def _novo_candidato_logado(cliente, cabecalho_chefe) -> dict[str, str]:
    resposta = novo_candidato(cliente, cabecalho_chefe)
    assert resposta.status_code == 201, resposta.text
    return login(cliente, resposta.json()["cpf"], SENHA_CANDIDATO)
