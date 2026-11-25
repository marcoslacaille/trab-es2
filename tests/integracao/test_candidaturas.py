from tests.auxiliares import (
    SENHA_CANDIDATO,
    eleicao_aberta_com_candidatos,
    login,
    nova_candidatura,
    nova_eleicao,
    novo_candidato,
    novo_partido,
)

ELEICOES = "/api/v1/eleicoes"
MINHAS = "/api/v1/candidaturas/minhas"


def rota(eleicao_id: int = 1, candidatura_id: int | None = None) -> str:
    base = f"{ELEICOES}/{eleicao_id}/candidaturas"
    return base if candidatura_id is None else f"{base}/{candidatura_id}"


def codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def criar_ids(cliente, cabecalho) -> tuple[int, int]:
    """Cria um candidato e um partido e devolve (candidato_id, partido_id)."""
    candidato = novo_candidato(cliente, cabecalho).json()["id"]
    partido = novo_partido(cliente, cabecalho).json()["id"]
    return candidato, partido


def test_chefe_cria_e_edita_candidatura(cliente, cabecalho_chefe):
    """RN-40: cria (201 com candidato e partido para exibição), edita e lista na ordem da urna."""
    nova_eleicao(cliente, cabecalho_chefe)
    candidato = novo_candidato(cliente, cabecalho_chefe, nome_urna="Carlos Lima").json()
    partido = novo_partido(cliente, cabecalho_chefe, sigla="PINO", numero=10).json()

    criada = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=candidato["id"], partido_id=partido["id"]
    )

    assert criada.status_code == 201, criada.text
    assert criada.json() == {
        "id": 1,
        "eleicao_id": 1,
        "cargo": "PRESIDENTE",
        "numero": "10",
        "candidato": {"id": candidato["id"], "nome_urna": "Carlos Lima"},
        "partido": {"id": partido["id"], "sigla": "PINO", "numero": 10},
    }

    # O PATCH muda cargo, número e partido; candidato e eleição não mudam (422).
    outro_partido = novo_partido(cliente, cabecalho_chefe).json()
    editada = cliente.patch(
        rota(1, 1),
        json={"cargo": "GOVERNADOR", "numero": "55", "partido_id": outro_partido["id"]},
        headers=cabecalho_chefe,
    )
    assert editada.status_code == 200, editada.text
    corpo = editada.json()
    assert (corpo["cargo"], corpo["numero"]) == ("GOVERNADOR", "55")
    assert corpo["partido"]["id"] == outro_partido["id"]
    assert corpo["candidato"] == criada.json()["candidato"]
    for proibido in ({"candidato_id": 5}, {"eleicao_id": 2}):
        recusada = cliente.patch(rota(1, 1), json=proibido, headers=cabecalho_chefe)
        assert (recusada.status_code, codigo(recusada)) == (422, "DADOS_INVALIDOS")

    # A lista sai na ordem da urna (cargo, depois número) e `?cargo=` filtra.
    for cargo, numero in [
        ("PRESIDENTE", "20"),
        ("SENADOR", "202"),
        ("PRESIDENTE", "10"),
        ("DEPUTADO_FEDERAL", "1234"),
        ("SENADOR", "101"),
    ]:
        resposta = nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero)
        assert resposta.status_code == 201, resposta.text
    todas = cliente.get(rota(), headers=cabecalho_chefe).json()
    senadores = cliente.get(f"{rota()}?cargo=SENADOR", headers=cabecalho_chefe).json()
    assert [(c["cargo"], c["numero"]) for c in todas] == [
        ("DEPUTADO_FEDERAL", "1234"),
        ("SENADOR", "101"),
        ("SENADOR", "202"),
        ("GOVERNADOR", "55"),
        ("PRESIDENTE", "10"),
        ("PRESIDENTE", "20"),
    ]
    assert [c["numero"] for c in senadores] == ["101", "202"]
    assert cliente.get(f"{rota()}?cargo=PREFEITO", headers=cabecalho_chefe).status_code == 422
    inexistente = cliente.get(rota(99), headers=cabecalho_chefe)
    assert (inexistente.status_code, codigo(inexistente)) == (404, "ELEICAO_NAO_ENCONTRADA")


def test_remover_candidatura_libera_o_numero_e_o_candidato(cliente, cabecalho_chefe):
    """RN-40: DELETE → 204; depois o número e o candidato podem ser usados de novo."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    criada = nova_candidatura(cliente, cabecalho_chefe).json()

    remocao = cliente.delete(rota(1, criada["id"]), headers=cabecalho_chefe)
    recriada = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=criada["candidato"]["id"], numero="10"
    )

    assert remocao.status_code == 204
    assert remocao.content == b""
    assert recriada.status_code == 201, recriada.text

    # Candidatura inexistente (ou de outra eleição) dá 404, tanto para editar quanto para remover.
    editar = cliente.patch(rota(1, 99), json={"numero": "11"}, headers=cabecalho_chefe)
    de_outra_eleicao = cliente.delete(rota(2, recriada.json()["id"]), headers=cabecalho_chefe)
    sem_eleicao = cliente.delete(rota(99, 1), headers=cabecalho_chefe)
    assert (editar.status_code, codigo(editar)) == (404, "CANDIDATURA_NAO_ENCONTRADA")
    assert (de_outra_eleicao.status_code, codigo(de_outra_eleicao)) == (
        404,
        "CANDIDATURA_NAO_ENCONTRADA",
    )
    assert codigo(sem_eleicao) == "ELEICAO_NAO_ENCONTRADA"


def test_numero_ou_cargo_invalido_responde_422(cliente, cabecalho_chefe):
    """RN-41 e RN-42: número com dígitos errados para o cargo ou cargo fora do enum → 422."""
    nova_eleicao(cliente, cabecalho_chefe)
    com_digitos_errados = [
        ("PRESIDENTE", "1"),
        ("PRESIDENTE", "123"),
        ("PRESIDENTE", "05"),
        ("GOVERNADOR", "1a"),
        ("SENADOR", "10"),
        ("SENADOR", "1234"),
        ("DEPUTADO_FEDERAL", "123"),
        ("DEPUTADO_ESTADUAL", "1234"),
        ("DEPUTADO_ESTADUAL", "01234"),
    ]

    for cargo, numero in com_digitos_errados:
        resposta = nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero)

        assert resposta.status_code == 422, (cargo, numero)
        assert codigo(resposta) == "NUMERO_INVALIDO_PARA_CARGO", (cargo, numero)
        assert resposta.json()["erro"]["detalhes"]["cargo"] == cargo

    invalido = nova_candidatura(cliente, cabecalho_chefe, cargo="PREFEITO", numero="13")
    assert (invalido.status_code, codigo(invalido)) == (422, "DADOS_INVALIDOS")
    for cargo, numero in [
        ("PRESIDENTE", "13"),
        ("GOVERNADOR", "13"),
        ("SENADOR", "123"),
        ("DEPUTADO_FEDERAL", "1234"),
        ("DEPUTADO_ESTADUAL", "12345"),
    ]:
        resposta = nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero)
        assert resposta.status_code == 201, (cargo, resposta.text)


def test_numero_repetido_no_mesmo_cargo_responde_409(cliente, cabecalho_chefe):
    """RN-43 e RN-44: número único por cargo e um candidato por eleição, na criação e na edição."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    primeira = nova_candidatura(cliente, cabecalho_chefe, numero="10").json()
    assert nova_candidatura(cliente, cabecalho_chefe, numero="20").status_code == 201

    repetido = nova_candidatura(cliente, cabecalho_chefe, numero="10")
    outro_cargo = nova_candidatura(cliente, cabecalho_chefe, cargo="GOVERNADOR", numero="10")
    assert (repetido.status_code, codigo(repetido)) == (409, "NUMERO_JA_UTILIZADO")
    assert outro_cargo.status_code == 201

    # Na edição, a própria candidatura é ignorada; o número de outra continua barrado.
    proprio = cliente.patch(rota(1, primeira["id"]), json={"numero": "10"}, headers=cabecalho_chefe)
    de_outra = cliente.patch(
        rota(1, primeira["id"]), json={"numero": "20"}, headers=cabecalho_chefe
    )
    assert proprio.status_code == 200
    assert (de_outra.status_code, codigo(de_outra)) == (409, "NUMERO_JA_UTILIZADO")

    # No máximo uma candidatura por candidato na eleição (mesmo noutro cargo); a unicidade
    # dos dois é por eleição, então o mesmo candidato e o mesmo número valem na outra.
    candidato_id = primeira["candidato"]["id"]
    duplicada = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=candidato_id, cargo="GOVERNADOR", numero="30"
    )
    em_outra_eleicao = nova_candidatura(
        cliente, cabecalho_chefe, eleicao_id=2, candidato_id=candidato_id, numero="10"
    )
    assert (duplicada.status_code, codigo(duplicada)) == (409, "CANDIDATURA_DUPLICADA")
    assert em_outra_eleicao.status_code == 201


def test_candidato_ou_partido_inexistente_responde_422(cliente, cabecalho_chefe):
    """RN-46: referência inexistente → 422 `REFERENCIA_INEXISTENTE` com `detalhes.campo`."""
    nova_eleicao(cliente, cabecalho_chefe)
    candidato_id, partido_id = criar_ids(cliente, cabecalho_chefe)

    sem_candidato = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=9999, partido_id=partido_id
    )
    sem_partido = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=candidato_id, partido_id=9999
    )

    for resposta, campo in ((sem_candidato, "candidato_id"), (sem_partido, "partido_id")):
        assert resposta.status_code == 422
        assert codigo(resposta) == "REFERENCIA_INEXISTENTE"
        assert resposta.json()["erro"]["detalhes"] == {"campo": campo}

    criada = nova_candidatura(cliente, cabecalho_chefe).json()
    editada = cliente.patch(
        rota(1, criada["id"]), json={"partido_id": 9999}, headers=cabecalho_chefe
    )
    assert (editada.status_code, codigo(editada)) == (422, "REFERENCIA_INEXISTENTE")


def test_candidatura_so_muda_com_a_eleicao_agendada(cliente, cabecalho_chefe):
    """RN-40: com a eleição ABERTA ou ENCERRADA, criar, editar e remover dão 409."""
    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    eleicao_id = aberta["eleicao_id"]
    existente = aberta["candidaturas"]["PRESIDENTE"]["10"]

    criar = nova_candidatura(cliente, cabecalho_chefe, eleicao_id, cargo="SENADOR", numero="303")
    editar = cliente.patch(
        rota(eleicao_id, existente), json={"numero": "11"}, headers=cabecalho_chefe
    )
    remover = cliente.delete(rota(eleicao_id, existente), headers=cabecalho_chefe)

    for resposta in (criar, editar, remover):
        assert resposta.status_code == 409
        assert codigo(resposta) == "ELEICAO_NAO_EDITAVEL"
        assert resposta.json()["erro"]["detalhes"] == {"status": "ABERTA"}
    assert len(cliente.get(rota(eleicao_id), headers=cabecalho_chefe).json()) == 4

    encerramento = cliente.post(f"{ELEICOES}/{eleicao_id}/encerramento", headers=cabecalho_chefe)
    assert encerramento.status_code == 200
    depois = nova_candidatura(cliente, cabecalho_chefe, eleicao_id, cargo="SENADOR", numero="303")
    assert (depois.status_code, codigo(depois)) == (409, "ELEICAO_NAO_EDITAVEL")
    assert depois.json()["erro"]["detalhes"] == {"status": "ENCERRADA"}


def test_segundo_turno_recusa_senador_e_terceiro_presidente(cliente, cabecalho_chefe):
    """RN-45: no 2º turno, Senador e o 3º Presidente dão 409; vale também ao trocar o turno."""
    nova_eleicao(cliente, cabecalho_chefe, turno=2)

    senador = nova_candidatura(cliente, cabecalho_chefe, cargo="SENADOR", numero="101")
    assert nova_candidatura(cliente, cabecalho_chefe, numero="10").status_code == 201
    assert nova_candidatura(cliente, cabecalho_chefe, numero="20").status_code == 201
    terceiro = nova_candidatura(cliente, cabecalho_chefe, numero="30")
    governador = nova_candidatura(cliente, cabecalho_chefe, cargo="GOVERNADOR", numero="10")

    assert (senador.status_code, codigo(senador)) == (409, "CARGO_NAO_PERMITIDO_NO_TURNO")
    assert (terceiro.status_code, codigo(terceiro)) == (409, "LIMITE_SEGUNDO_TURNO")
    assert governador.status_code == 201  # o limite é por cargo

    # O PATCH de turno 1 → 2 não pode criar um 2º turno com Senador ou com 3 Presidentes.
    incompativeis = [
        ([("SENADOR", "101"), ("PRESIDENTE", "10")], "CARGO_NAO_PERMITIDO_NO_TURNO"),
        (
            [("PRESIDENTE", "10"), ("PRESIDENTE", "20"), ("PRESIDENTE", "30")],
            "LIMITE_SEGUNDO_TURNO",
        ),
    ]
    for dia, (candidaturas, esperado) in enumerate(incompativeis, start=1):
        eleicao_id = nova_eleicao(cliente, cabecalho_chefe, data=f"2026-12-0{dia}").json()["id"]
        for cargo, numero in candidaturas:
            resposta = nova_candidatura(
                cliente, cabecalho_chefe, eleicao_id, cargo=cargo, numero=numero
            )
            assert resposta.status_code == 201, resposta.text

        troca = cliente.patch(
            f"{ELEICOES}/{eleicao_id}", json={"turno": 2}, headers=cabecalho_chefe
        )

        assert (troca.status_code, codigo(troca)) == (409, esperado)
        assert cliente.get(f"{ELEICOES}/{eleicao_id}", headers=cabecalho_chefe).json()["turno"] == 1


def test_candidato_ve_so_as_proprias_candidaturas(cliente, cabecalho_chefe, cabecalho_candidato):
    """RN-47: `/candidaturas/minhas` lista as do candidato logado, em todas as eleições."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    dono = novo_candidato(cliente, cabecalho_chefe, nome_urna="Carlos Lima").json()
    partido = novo_partido(cliente, cabecalho_chefe, sigla="PINO", numero=10).json()
    nova_candidatura(cliente, cabecalho_chefe, 2, candidato_id=dono["id"], partido_id=partido["id"])
    nova_candidatura(
        cliente, cabecalho_chefe, 1, candidato_id=dono["id"], partido_id=partido["id"], numero="13"
    )
    nova_candidatura(cliente, cabecalho_chefe, 1, numero="20")  # de outro candidato
    cabecalho_dono = login(cliente, dono["cpf"], SENHA_CANDIDATO)

    resposta = cliente.get(MINHAS, headers=cabecalho_dono)

    assert resposta.status_code == 200, resposta.text
    assert [(c["eleicao_id"], c["cargo"], c["numero"]) for c in resposta.json()] == [
        (1, "PRESIDENTE", "13"),
        (2, "PRESIDENTE", "10"),
    ]
    assert resposta.json()[0]["candidato"] == {"id": dono["id"], "nome_urna": "Carlos Lima"}
    assert resposta.json()[0]["partido"]["sigla"] == "PINO"

    sem_candidatura = cliente.get(MINHAS, headers=cabecalho_candidato)
    assert sem_candidatura.status_code == 200
    assert sem_candidatura.json() == []
