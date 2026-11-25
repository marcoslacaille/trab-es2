"""TI-74: o roteiro da demonstração, de ponta a ponta."""

from tests.auxiliares import (
    SENHA_CANDIDATO,
    SENHA_ELEITOR,
    login,
    nova_candidatura,
    novo_candidato,
    novo_eleitor,
    novo_partido,
    votar,
)

API = "/api/v1"
ELEITORES = {
    "Ana": ("Ana Beatriz Souza", "011.524.493-03", "100000000001", "1990-04-12"),
    "Bruno": ("Bruno Almeida", "341.672.110-17", "100000000002", "1985-09-30"),
    "Camila": ("Camila Rocha", "945.807.302-24", "100000000003", "2001-01-15"),
    "Diego": ("Diego Martins", "917.400.297-04", "100000000004", "1978-06-22"),
    "Elisa": ("Elisa Ferreira", "526.018.159-06", "100000000005", "2008-02-10"),
    "Fabio": ("Fábio Nunes", "356.230.123-53", "100000000006", "1960-12-03"),
}
# (cargo, número, nome de urna, nome completo, CPF, nascimento, número do partido)
CANDIDATURAS = [
    (
        "PRESIDENTE",
        "10",
        "Carlos Lima",
        "Carlos Henrique Lima",
        "398.259.791-94",
        "1968-03-05",
        10,
    ),
    (
        "PRESIDENTE",
        "20",
        "Marina Costa",
        "Marina Costa Ribeiro",
        "795.422.058-30",
        "1972-07-19",
        20,
    ),
    (
        "GOVERNADOR",
        "10",
        "Ricardo Souza",
        "Ricardo Souza Neto",
        "906.790.377-99",
        "1965-11-11",
        10,
    ),
    (
        "GOVERNADOR",
        "30",
        "Helena Prado",
        "Helena Prado Antunes",
        "787.789.328-07",
        "1975-05-02",
        30,
    ),
    (
        "SENADOR",
        "202",
        "Paulo Mendes",
        "Paulo Roberto Mendes",
        "748.526.057-00",
        "1959-08-08",
        20,
    ),
    (
        "SENADOR",
        "303",
        "Lúcia Ramos",
        "Lúcia Ramos Vieira",
        "442.323.221-91",
        "1970-10-10",
        30,
    ),
]


def _cadastrar_eleitores(cliente, chefe) -> dict[str, dict]:
    """Cadastra os 6 eleitores do seed pela API e devolve o cabeçalho de login de cada um."""
    cabecalhos = {}
    for apelido, (nome, cpf, titulo, nascimento) in ELEITORES.items():
        resposta = novo_eleitor(
            cliente, chefe, nome=nome, cpf=cpf, titulo_eleitor=titulo, data_nascimento=nascimento
        )
        assert resposta.status_code == 201, resposta.text
        assert "senha" not in resposta.text
        cabecalhos[apelido] = login(cliente, cpf.replace(".", "").replace("-", ""), SENHA_ELEITOR)
    return cabecalhos


def _montar_eleicao(cliente, chefe) -> int:
    """Cria partidos, candidatos, a eleição do dia e as 6 candidaturas. Devolve o id da eleição."""
    partidos = {}
    for sigla, numero in [("PINO", 10), ("UC", 20), ("MV", 30)]:
        resposta = novo_partido(cliente, chefe, sigla=sigla, nome=f"Partido {sigla}", numero=numero)
        assert resposta.status_code == 201, resposta.text
        partidos[numero] = resposta.json()["id"]
    eleicao = cliente.post(
        f"{API}/eleicoes",
        json={
            "descricao": "Eleições Gerais 2026 — 1º turno (simulação)",
            "data": "2026-11-25",
            "turno": 1,
            "horario_abertura": "08:00",
            "horario_encerramento": "17:00",
        },
        headers=chefe,
    )
    assert eleicao.status_code == 201, eleicao.text
    assert eleicao.json()["status"] == "AGENDADA"
    eleicao_id = eleicao.json()["id"]
    for cargo, numero, urna, nome, cpf, nascimento, numero_partido in CANDIDATURAS:
        candidato = novo_candidato(
            cliente, chefe, nome=nome, nome_urna=urna, cpf=cpf, data_nascimento=nascimento
        )
        assert candidato.status_code == 201, candidato.text
        candidatura = nova_candidatura(
            cliente,
            chefe,
            eleicao_id,
            candidato_id=candidato.json()["id"],
            partido_id=partidos[numero_partido],
            cargo=cargo,
            numero=numero,
        )
        assert candidatura.status_code == 201, candidatura.text
    return eleicao_id


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def test_ti74_parte1_perfis_e_cadastros_do_chefe(cliente, cabecalho_chefe):
    """TI-74 (parte 1, itens 1 a 10): cadastros, validações, 2º turno e abertura da eleição."""
    chefe = cabecalho_chefe
    _cadastrar_eleitores(cliente, chefe)
    eleicao_id = _montar_eleicao(cliente, chefe)

    listagem = cliente.get(f"{API}/eleitores?pagina=1&tamanho=5", headers=chefe)
    assert listagem.status_code == 200
    assert listagem.json()["total"] == 6 and len(listagem.json()["itens"]) == 5

    igor = novo_eleitor(cliente, chefe, nome="Igor Barbosa", cpf="081.836.584-66")
    assert igor.status_code == 201, igor.text
    cpf_ruim = novo_eleitor(cliente, chefe, cpf="111.111.111-11")
    assert (cpf_ruim.status_code, _codigo(cpf_ruim)) == (422, "CPF_INVALIDO")
    menor = novo_eleitor(cliente, chefe, data_nascimento="2015-01-01")
    assert (menor.status_code, _codigo(menor)) == (422, "IDADE_MINIMA")

    renata = novo_candidato(
        cliente, chefe, nome="Renata Campos", nome_urna="Renata Campos", cpf="241.592.066-54"
    )
    assert renata.status_code == 201, renata.text

    segundo_turno = cliente.post(
        f"{API}/eleicoes",
        json={
            "descricao": "Segundo turno",
            "data": "2026-11-26",
            "turno": 2,
            "horario_abertura": "08:00",
            "horario_encerramento": "17:00",
        },
        headers=chefe,
    )
    assert segundo_turno.status_code == 201, segundo_turno.text
    assert segundo_turno.json()["links"]
    cargo_proibido = nova_candidatura(
        cliente,
        chefe,
        segundo_turno.json()["id"],
        candidato_id=renata.json()["id"],
        cargo="SENADOR",
        numero="404",
    )
    assert (cargo_proibido.status_code, _codigo(cargo_proibido)) == (
        409,
        "CARGO_NAO_PERMITIDO_NO_TURNO",
    )

    antes = cliente.get(f"{API}/eleicoes/{eleicao_id}", headers=chefe).json()
    assert antes["status"] == "AGENDADA"
    assert "abrir" in {link["rel"] for link in antes["links"]}
    aberta = cliente.post(f"{API}/eleicoes/{eleicao_id}/abertura", headers=chefe)
    assert aberta.status_code == 200 and aberta.json()["status"] == "ABERTA"
    assert "encerrar" in {link["rel"] for link in aberta.json()["links"]}
    congelada = nova_candidatura(cliente, chefe, eleicao_id, numero="99")
    assert (congelada.status_code, _codigo(congelada)) == (409, "ELEICAO_NAO_EDITAVEL")


def test_ti74_partes2_a_4_votacao_acompanhamento_e_resultado(cliente, cabecalho_chefe, relogio):
    """TI-74 (partes 2 a 4, itens 11 a 27): votação, parcial, encerramento e resultado."""
    chefe = cabecalho_chefe
    eleitores = _cadastrar_eleitores(cliente, chefe)
    eleicao_id = _montar_eleicao(cliente, chefe)
    assert cliente.post(f"{API}/eleicoes/{eleicao_id}/abertura", headers=chefe).status_code == 200
    votacao = f"{API}/votacao/eleicoes/{eleicao_id}"
    ana = eleitores["Ana"]

    # Parte 2: Ana vota (itens 11 a 17)
    cedula = cliente.get(f"{votacao}/cedula", headers=ana)
    assert cedula.status_code == 200
    assert [c["cargo"] for c in cedula.json()["cargos"]] == ["SENADOR", "GOVERNADOR", "PRESIDENTE"]
    registro = cliente.post(
        f"{votacao}/votos/registro",
        json={"cargo": "PRESIDENTE", "modo": "NUMERO", "numero": "10"},
        headers=ana,
    )
    assert registro.status_code == 200
    assert registro.json()["tipo_voto"] == "NOMINAL"
    assert registro.json()["candidato"]["nome_urna"] == "Carlos Lima"
    token = registro.json()["token_cedula"]
    confirmacao = cliente.post(
        f"{votacao}/votos/confirmacao", json={"token_cedula": token}, headers=ana
    )
    assert confirmacao.status_code == 201
    assert "Carlos" not in confirmacao.text and "candidato" not in confirmacao.json()
    repetido = cliente.post(
        f"{votacao}/votos/confirmacao", json={"token_cedula": token}, headers=ana
    )
    assert (repetido.status_code, _codigo(repetido)) == (409, "VOTO_JA_REGISTRADO")
    assert votar(cliente, ana, eleicao_id, "SENADOR", branco=True).status_code == 201
    nulo = cliente.post(
        f"{votacao}/votos/registro",
        json={"cargo": "GOVERNADOR", "modo": "NUMERO", "numero": "99"},
        headers=ana,
    )
    assert (nulo.status_code, nulo.json()["tipo_voto"]) == (200, "NULO")
    assert (
        cliente.post(
            f"{votacao}/votos/confirmacao",
            json={"token_cedula": nulo.json()["token_cedula"]},
            headers=ana,
        ).status_code
        == 201
    )
    assert votar(cliente, eleitores["Bruno"], eleicao_id, "PRESIDENTE", "20").status_code == 201
    assert votar(cliente, eleitores["Camila"], eleicao_id, "PRESIDENTE", "10").status_code == 201
    chefe_votando = cliente.post(
        f"{votacao}/votos/registro",
        json={"cargo": "PRESIDENTE", "modo": "BRANCO"},
        headers=chefe,
    )
    assert (chefe_votando.status_code, _codigo(chefe_votando)) == (403, "PERFIL_NAO_AUTORIZADO")
    relogio.avancar(minutes=5)  # cadastrado no mesmo instante da abertura ainda seria apto
    gustavo = novo_eleitor(
        cliente, chefe, nome="Gustavo Pereira", cpf="217.533.772-34", titulo_eleitor="100000000007"
    )
    assert gustavo.status_code == 201, gustavo.text
    cabecalho_gustavo = login(cliente, "21753377234", SENHA_ELEITOR)
    nao_apto = cliente.get(f"{votacao}/cedula", headers=cabecalho_gustavo)
    assert nao_apto.status_code == 403, nao_apto.text
    assert _codigo(nao_apto) == "ELEITOR_NAO_APTO"

    # Parte 3: acompanhamento (itens 21 a 24)
    parcial = cliente.get(f"{API}/apuracao/eleicoes/{eleicao_id}/parcial", headers=ana)
    assert parcial.status_code == 200 and parcial.json()["tipo"] == "PARCIAL"
    assert parcial.json()["comparecimento"] == {
        "eleitores_aptos": 6,
        "votantes": 3,
        "abstencao": 3,
    }
    presidente = next(c for c in parcial.json()["cargos"] if c["cargo"] == "PRESIDENTE")
    assert {c["numero"]: c["votos"] for c in presidente["candidatos"]} == {"10": 2, "20": 1}
    carlos = login(cliente, "39825979194", SENHA_CANDIDATO)
    do_candidato = cliente.get(f"{API}/apuracao/eleicoes/{eleicao_id}/parcial", headers=carlos)
    assert [c["cargo"] for c in do_candidato.json()["cargos"]] == ["PRESIDENTE"]
    outro_cargo = cliente.get(
        f"{API}/apuracao/eleicoes/{eleicao_id}/parcial?cargo=SENADOR", headers=carlos
    )
    assert (outro_cargo.status_code, _codigo(outro_cargo)) == (403, "CARGO_NAO_PERMITIDO")
    cedo = cliente.get(f"{API}/apuracao/eleicoes/{eleicao_id}/resultado", headers=ana)
    assert (cedo.status_code, _codigo(cedo)) == (409, "APURACAO_INDISPONIVEL")

    # Parte 4: encerramento e resultado final (itens 25 a 27)
    encerrada = cliente.post(f"{API}/eleicoes/{eleicao_id}/encerramento", headers=chefe)
    assert encerrada.status_code == 200 and encerrada.json()["status"] == "ENCERRADA"
    tarde = votar(cliente, eleitores["Diego"], eleicao_id, "PRESIDENTE", "10")
    assert (tarde.status_code, _codigo(tarde)) == (409, "ELEICAO_NAO_ABERTA")
    final = cliente.get(f"{API}/apuracao/eleicoes/{eleicao_id}/resultado", headers=chefe)
    assert final.status_code == 200 and final.json()["tipo"] == "FINAL"
    assert final.json()["comparecimento"]["abstencao"] == 3
    presidente = next(c for c in final.json()["cargos"] if c["cargo"] == "PRESIDENTE")
    assert presidente["mais_votado"]["nome_urna"] == "Carlos Lima"
    assert presidente["situacao"] == "DEFINIDO"
