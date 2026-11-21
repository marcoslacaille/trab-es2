import pytest

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


# ---------------------------------------------------------------- TI-30


def test_ti30_chefe_cria_candidatura_valida(cliente, cabecalho_chefe):
    """TI-30 / RN-40: criar candidatura válida → 201 com candidato e partido para exibição."""
    nova_eleicao(cliente, cabecalho_chefe)
    candidato = novo_candidato(cliente, cabecalho_chefe, nome_urna="Carlos Lima").json()
    partido = novo_partido(cliente, cabecalho_chefe, sigla="PINO", numero=10).json()

    resposta = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=candidato["id"], partido_id=partido["id"]
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json() == {
        "id": 1,
        "eleicao_id": 1,
        "cargo": "PRESIDENTE",
        "numero": "10",
        "candidato": {"id": candidato["id"], "nome_urna": "Carlos Lima"},
        "partido": {"id": partido["id"], "sigla": "PINO", "numero": 10},
    }


def test_ti30_so_o_chefe_gerencia_candidaturas(
    cliente, cabecalho_chefe, cabecalho_eleitor, cabecalho_candidato
):
    """RN-40: eleitor e candidato recebem 403 em todas as rotas; sem token, 401."""
    nova_eleicao(cliente, cabecalho_chefe)
    assert nova_candidatura(cliente, cabecalho_chefe).status_code == 201
    corpo = {"candidato_id": 1, "partido_id": 1, "cargo": "PRESIDENTE", "numero": "11"}

    for cabecalho in (cabecalho_eleitor, cabecalho_candidato, {}):
        esperado = 401 if not cabecalho else 403
        assert cliente.get(rota(), headers=cabecalho).status_code == esperado
        assert cliente.post(rota(), json=corpo, headers=cabecalho).status_code == esperado
        assert cliente.patch(rota(1, 1), json={}, headers=cabecalho).status_code == esperado
        assert cliente.delete(rota(1, 1), headers=cabecalho).status_code == esperado


def test_ti30_lista_ordenada_por_cargo_e_numero_com_filtro(cliente, cabecalho_chefe):
    """RN-40: lista na ordem da urna (cargo, depois número); `?cargo=` filtra; id ruim → 404/422."""
    nova_eleicao(cliente, cabecalho_chefe)
    for cargo, numero in [
        ("PRESIDENTE", "20"),
        ("SENADOR", "202"),
        ("PRESIDENTE", "10"),
        ("DEPUTADO_FEDERAL", "1234"),
        ("SENADOR", "101"),
    ]:
        assert (
            nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero).status_code
            == 201
        )

    todas = cliente.get(rota(), headers=cabecalho_chefe).json()
    senadores = cliente.get(f"{rota()}?cargo=SENADOR", headers=cabecalho_chefe).json()

    assert [(c["cargo"], c["numero"]) for c in todas] == [
        ("DEPUTADO_FEDERAL", "1234"),
        ("SENADOR", "101"),
        ("SENADOR", "202"),
        ("PRESIDENTE", "10"),
        ("PRESIDENTE", "20"),
    ]
    assert [c["numero"] for c in senadores] == ["101", "202"]
    assert cliente.get(f"{rota()}?cargo=PREFEITO", headers=cabecalho_chefe).status_code == 422
    inexistente = cliente.get(rota(99), headers=cabecalho_chefe)
    assert (inexistente.status_code, codigo(inexistente)) == (404, "ELEICAO_NAO_ENCONTRADA")


def test_ti30_editar_cargo_numero_e_partido(cliente, cabecalho_chefe):
    """RN-40: o PATCH muda cargo, número e partido; candidato e eleição não mudam (422)."""
    nova_eleicao(cliente, cabecalho_chefe)
    criada = nova_candidatura(cliente, cabecalho_chefe).json()
    outro_partido = novo_partido(cliente, cabecalho_chefe).json()

    resposta = cliente.patch(
        rota(1, criada["id"]),
        json={"cargo": "GOVERNADOR", "numero": "55", "partido_id": outro_partido["id"]},
        headers=cabecalho_chefe,
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert (corpo["cargo"], corpo["numero"]) == ("GOVERNADOR", "55")
    assert corpo["partido"]["id"] == outro_partido["id"]
    assert corpo["candidato"] == criada["candidato"]
    for proibido in ({"candidato_id": 5}, {"eleicao_id": 2}):
        recusada = cliente.patch(rota(1, criada["id"]), json=proibido, headers=cabecalho_chefe)
        assert (recusada.status_code, codigo(recusada)) == (422, "DADOS_INVALIDOS")


def test_ti30_editar_ou_remover_candidatura_inexistente_da_404(cliente, cabecalho_chefe):
    """404 `CANDIDATURA_NAO_ENCONTRADA`, inclusive para candidatura de outra eleição."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    criada = nova_candidatura(cliente, cabecalho_chefe, eleicao_id=1).json()

    editar = cliente.patch(rota(1, 99), json={"numero": "11"}, headers=cabecalho_chefe)
    remover = cliente.delete(rota(2, criada["id"]), headers=cabecalho_chefe)

    assert (editar.status_code, codigo(editar)) == (404, "CANDIDATURA_NAO_ENCONTRADA")
    assert (remover.status_code, codigo(remover)) == (404, "CANDIDATURA_NAO_ENCONTRADA")
    sem_eleicao = cliente.delete(rota(99, 1), headers=cabecalho_chefe)
    assert codigo(sem_eleicao) == "ELEICAO_NAO_ENCONTRADA"


def test_ti30_remover_candidatura_libera_o_numero_e_o_candidato(cliente, cabecalho_chefe):
    """RN-40: DELETE → 204; depois o número e o candidato podem ser usados de novo."""
    nova_eleicao(cliente, cabecalho_chefe)
    criada = nova_candidatura(cliente, cabecalho_chefe).json()

    remocao = cliente.delete(rota(1, criada["id"]), headers=cabecalho_chefe)
    recriada = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=criada["candidato"]["id"], numero="10"
    )

    assert remocao.status_code == 204
    assert remocao.content == b""
    assert recriada.status_code == 201, recriada.text


# ---------------------------------------------------------------- TI-31


@pytest.mark.parametrize(
    ("cargo", "numero"),
    [
        ("PRESIDENTE", "1"),
        ("PRESIDENTE", "123"),
        ("PRESIDENTE", "05"),
        ("GOVERNADOR", "1a"),
        ("SENADOR", "10"),
        ("SENADOR", "1234"),
        ("DEPUTADO_FEDERAL", "123"),
        ("DEPUTADO_ESTADUAL", "1234"),
        ("DEPUTADO_ESTADUAL", "01234"),
    ],
)
def test_ti31_numero_com_digitos_errados_para_o_cargo_da_422(
    cliente, cabecalho_chefe, cargo, numero
):
    """TI-31 / RN-42: quantidade de dígitos errada, zero à esquerda ou letras → 422."""
    nova_eleicao(cliente, cabecalho_chefe)

    resposta = nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero)

    assert resposta.status_code == 422
    assert codigo(resposta) == "NUMERO_INVALIDO_PARA_CARGO"
    assert resposta.json()["erro"]["detalhes"]["cargo"] == cargo


def test_ti31_numero_certo_de_cada_cargo_passa_e_cargo_invalido_da_422(cliente, cabecalho_chefe):
    """RN-41, RN-42: os 5 cargos aceitam o número certo; cargo fora do enum → 422."""
    nova_eleicao(cliente, cabecalho_chefe)
    for cargo, numero in [
        ("PRESIDENTE", "13"),
        ("GOVERNADOR", "13"),
        ("SENADOR", "123"),
        ("DEPUTADO_FEDERAL", "1234"),
        ("DEPUTADO_ESTADUAL", "12345"),
    ]:
        resposta = nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero)
        assert resposta.status_code == 201, (cargo, resposta.text)

    invalido = nova_candidatura(cliente, cabecalho_chefe, cargo="PREFEITO", numero="13")
    assert (invalido.status_code, codigo(invalido)) == (422, "DADOS_INVALIDOS")


# ---------------------------------------------------------------- TI-32


def test_ti32_numero_repetido_no_mesmo_cargo_da_409(cliente, cabecalho_chefe):
    """TI-32 / RN-43: mesmo número no mesmo cargo → 409; Presidente 10 e Governador 10 → 201."""
    nova_eleicao(cliente, cabecalho_chefe)
    assert nova_candidatura(cliente, cabecalho_chefe, numero="10").status_code == 201

    repetido = nova_candidatura(cliente, cabecalho_chefe, numero="10")
    outro_cargo = nova_candidatura(cliente, cabecalho_chefe, cargo="GOVERNADOR", numero="10")

    assert (repetido.status_code, codigo(repetido)) == (409, "NUMERO_JA_UTILIZADO")
    assert outro_cargo.status_code == 201


def test_ti32_editar_para_numero_de_outra_candidatura_da_409_mas_o_proprio_passa(
    cliente, cabecalho_chefe
):
    """RN-43: na edição, a própria candidatura é ignorada; o número de outra continua barrado."""
    nova_eleicao(cliente, cabecalho_chefe)
    primeira = nova_candidatura(cliente, cabecalho_chefe, numero="10").json()
    nova_candidatura(cliente, cabecalho_chefe, numero="20")

    proprio = cliente.patch(rota(1, primeira["id"]), json={"numero": "10"}, headers=cabecalho_chefe)
    de_outra = cliente.patch(
        rota(1, primeira["id"]), json={"numero": "20"}, headers=cabecalho_chefe
    )

    assert proprio.status_code == 200
    assert (de_outra.status_code, codigo(de_outra)) == (409, "NUMERO_JA_UTILIZADO")


def test_ti32_mesmo_numero_em_eleicoes_diferentes_e_permitido(cliente, cabecalho_chefe):
    """RN-43: a unicidade é por eleição."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)

    primeira = nova_candidatura(cliente, cabecalho_chefe, eleicao_id=1, numero="10")
    segunda = nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="10")

    assert primeira.status_code == segunda.status_code == 201


# ---------------------------------------------------------------- TI-33


def test_ti33_mesmo_candidato_duas_vezes_na_eleicao_da_409(cliente, cabecalho_chefe):
    """TI-33 / RN-44: no máximo uma candidatura por candidato na eleição (mesmo noutro cargo)."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    primeira = nova_candidatura(cliente, cabecalho_chefe).json()
    candidato_id = primeira["candidato"]["id"]

    repetida = nova_candidatura(
        cliente, cabecalho_chefe, candidato_id=candidato_id, cargo="GOVERNADOR", numero="20"
    )
    em_outra_eleicao = nova_candidatura(
        cliente, cabecalho_chefe, eleicao_id=2, candidato_id=candidato_id, numero="10"
    )

    assert (repetida.status_code, codigo(repetida)) == (409, "CANDIDATURA_DUPLICADA")
    assert em_outra_eleicao.status_code == 201


# ---------------------------------------------------------------- TI-34


def test_ti34_candidato_ou_partido_inexistente_da_422(cliente, cabecalho_chefe):
    """TI-34 / RN-46: referência inexistente → 422 `REFERENCIA_INEXISTENTE` com `detalhes.campo`."""
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


def test_ti34_editar_para_partido_inexistente_da_422(cliente, cabecalho_chefe):
    """RN-46 na edição: partido inexistente → 422 `REFERENCIA_INEXISTENTE`."""
    nova_eleicao(cliente, cabecalho_chefe)
    criada = nova_candidatura(cliente, cabecalho_chefe).json()

    resposta = cliente.patch(
        rota(1, criada["id"]), json={"partido_id": 9999}, headers=cabecalho_chefe
    )

    assert (resposta.status_code, codigo(resposta)) == (422, "REFERENCIA_INEXISTENTE")


# ---------------------------------------------------------------- TI-35


def test_ti35_criar_editar_e_remover_com_eleicao_aberta_da_409(cliente, cabecalho_chefe):
    """TI-35 / RN-40: com a eleição ABERTA, as três operações → 409 `ELEICAO_NAO_EDITAVEL`."""
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


def test_ti35_com_eleicao_encerrada_tambem_da_409(cliente, cabecalho_chefe):
    """RN-40: depois de encerrada, as candidaturas continuam congeladas."""
    aberta = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    eleicao_id = aberta["eleicao_id"]
    encerramento = cliente.post(f"{ELEICOES}/{eleicao_id}/encerramento", headers=cabecalho_chefe)
    assert encerramento.status_code == 200

    criar = nova_candidatura(cliente, cabecalho_chefe, eleicao_id, cargo="SENADOR", numero="303")

    assert (criar.status_code, codigo(criar)) == (409, "ELEICAO_NAO_EDITAVEL")
    assert criar.json()["erro"]["detalhes"] == {"status": "ENCERRADA"}


# ---------------------------------------------------------------- TI-36


def test_ti36_segundo_turno_recusa_senador_e_terceiro_presidente(cliente, cabecalho_chefe):
    """TI-36 / RN-45: 2º turno: Senador → 409; 3º candidato a Presidente → 409."""
    nova_eleicao(cliente, cabecalho_chefe, turno=2)

    senador = nova_candidatura(cliente, cabecalho_chefe, cargo="SENADOR", numero="101")
    assert nova_candidatura(cliente, cabecalho_chefe, numero="10").status_code == 201
    assert nova_candidatura(cliente, cabecalho_chefe, numero="20").status_code == 201
    terceiro = nova_candidatura(cliente, cabecalho_chefe, numero="30")
    governador = nova_candidatura(cliente, cabecalho_chefe, cargo="GOVERNADOR", numero="10")

    assert (senador.status_code, codigo(senador)) == (409, "CARGO_NAO_PERMITIDO_NO_TURNO")
    assert (terceiro.status_code, codigo(terceiro)) == (409, "LIMITE_SEGUNDO_TURNO")
    assert governador.status_code == 201  # o limite é por cargo


def test_ti36_primeiro_turno_aceita_qualquer_cargo_e_mais_de_dois(cliente, cabecalho_chefe):
    """RN-45 só vale no 2º turno: no 1º, Senador e 3 candidatos a Presidente passam."""
    nova_eleicao(cliente, cabecalho_chefe)

    for numero in ("10", "20", "30"):
        assert nova_candidatura(cliente, cabecalho_chefe, numero=numero).status_code == 201
    assert (
        nova_candidatura(cliente, cabecalho_chefe, cargo="SENADOR", numero="101").status_code == 201
    )


def test_ti36_segundo_turno_na_edicao_ignora_a_propria_candidatura(cliente, cabecalho_chefe):
    """RN-45: com 2 no cargo, editar uma delas não conta como 3ª; mudar para Senador → 409."""
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    primeira = nova_candidatura(cliente, cabecalho_chefe, numero="10").json()
    nova_candidatura(cliente, cabecalho_chefe, numero="20")

    renumerar = cliente.patch(
        rota(1, primeira["id"]), json={"numero": "11"}, headers=cabecalho_chefe
    )
    para_senador = cliente.patch(
        rota(1, primeira["id"]), json={"cargo": "SENADOR", "numero": "111"}, headers=cabecalho_chefe
    )

    assert renumerar.status_code == 200
    assert codigo(para_senador) == "CARGO_NAO_PERMITIDO_NO_TURNO"


def test_ti36_abrir_segundo_turno_exige_exatamente_dois_por_cargo(cliente, cabecalho_chefe):
    """TI-36 / RN-17: abrir com 1 candidato → 409 `SEGUNDO_TURNO_INCOMPLETO`; com 2, abre."""
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    nova_candidatura(cliente, cabecalho_chefe, numero="10")

    incompleto = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)
    nova_candidatura(cliente, cabecalho_chefe, numero="20")
    completo = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert (incompleto.status_code, codigo(incompleto)) == (409, "SEGUNDO_TURNO_INCOMPLETO")
    assert incompleto.json()["erro"]["detalhes"] == {"cargos": ["PRESIDENTE"]}
    assert completo.status_code == 200, completo.text
    assert completo.json()["status"] == "ABERTA"


# ---------------------------------------------------------------- TI-37


def test_ti37_candidato_ve_so_as_proprias_candidaturas(cliente, cabecalho_chefe):
    """TI-37 / RN-47: `/candidaturas/minhas` lista as do candidato logado, em todas as eleições."""
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


def test_ti37_candidato_sem_candidatura_recebe_lista_vazia(cliente, cabecalho_candidato):
    """RN-47: sem candidaturas → 200 com lista vazia."""
    resposta = cliente.get(MINHAS, headers=cabecalho_candidato)

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_ti37_so_o_candidato_acessa_minhas(cliente, cabecalho_chefe, cabecalho_eleitor):
    """RN-47: Chefe e Eleitor recebem 403; sem token, 401."""
    assert cliente.get(MINHAS, headers=cabecalho_chefe).status_code == 403
    assert cliente.get(MINHAS, headers=cabecalho_eleitor).status_code == 403
    assert cliente.get(MINHAS).status_code == 401


# ---------------------------------------------------------------- RN-45 na edição da eleição


@pytest.mark.parametrize(
    ("candidaturas", "codigo_esperado"),
    [
        ([("SENADOR", "101"), ("PRESIDENTE", "10")], "CARGO_NAO_PERMITIDO_NO_TURNO"),
        (
            [("PRESIDENTE", "10"), ("PRESIDENTE", "20"), ("PRESIDENTE", "30")],
            "LIMITE_SEGUNDO_TURNO",
        ),
    ],
)
def test_rn45_trocar_turno_para_2_com_candidaturas_incompativeis_e_recusado(
    cliente, cabecalho_chefe, candidaturas, codigo_esperado
):
    """RN-45: o PATCH de turno 1 → 2 não pode criar um 2º turno com Senador ou 3 Presidentes."""
    nova_eleicao(cliente, cabecalho_chefe)
    for cargo, numero in candidaturas:
        assert (
            nova_candidatura(cliente, cabecalho_chefe, cargo=cargo, numero=numero).status_code
            == 201
        )

    resposta = cliente.patch(f"{ELEICOES}/1", json={"turno": 2}, headers=cabecalho_chefe)

    assert (resposta.status_code, codigo(resposta)) == (409, codigo_esperado)
    assert cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()["turno"] == 1


def test_rn45_trocar_turno_para_2_com_candidaturas_compativeis_passa(cliente, cabecalho_chefe):
    """RN-45: com até 2 candidaturas de Presidente, a eleição pode virar 2º turno."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_candidatura(cliente, cabecalho_chefe, numero="10")
    nova_candidatura(cliente, cabecalho_chefe, numero="20")

    resposta = cliente.patch(f"{ELEICOES}/1", json={"turno": 2}, headers=cabecalho_chefe)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["turno"] == 2
