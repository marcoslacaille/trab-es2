from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database import SessionLocal
from tests.auxiliares import eleicao_aberta_com_candidatos, nova_candidatura, nova_eleicao

ELEICOES = "/api/v1/eleicoes"
FUSO = ZoneInfo("America/Sao_Paulo")


def instante(texto: str) -> datetime:
    """Lê o carimbo da resposta; o fuso (UTC ou Brasília) não importa, só o instante."""
    return datetime.fromisoformat(texto)


def rels(corpo: dict) -> list[str]:
    """Nomes dos links de uma resposta de eleição."""
    return [link["rel"] for link in corpo["links"]]


def marcar_encerrada(eleicao_id: int) -> None:
    """Muda o status direto no banco, só para montar o cenário do filtro da listagem.

    Só monta o cenário (uma segunda eleição já ENCERRADA, sem precisar de 2 candidaturas por
    cargo no 2º turno); nenhuma regra é contornada. As datas respeitam
    `ck_eleicoes_status_coerente`.
    """
    with SessionLocal() as sessao:
        sessao.execute(
            text(
                "UPDATE eleicoes SET status = 'ENCERRADA', aberta_em = now(), "
                "encerrada_em = now() WHERE id = :id"
            ),
            {"id": eleicao_id},
        )
        sessao.commit()


def test_chefe_cria_eleicao_agendada_com_link_abrir(cliente, cabecalho_chefe):
    """RN-10 e RN-19: criar → 201, AGENDADA, sem carimbos e com o link `abrir`."""
    resposta = nova_eleicao(cliente, cabecalho_chefe)

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["id"] == 1
    assert corpo["status"] == "AGENDADA"
    assert corpo["aberta_em"] is None and corpo["encerrada_em"] is None
    assert corpo["horario_abertura"] == "08:00:00"
    assert corpo["horario_encerramento"] == "17:00:00"
    assert rels(corpo) == ["self", "editar", "candidaturas", "nova-candidatura", "abrir"]
    assert {"rel": "abrir", "metodo": "POST", "href": "/api/v1/eleicoes/1/abertura"} in corpo[
        "links"
    ]


def test_schema_recusa_horario_com_fuso_e_campo_desconhecido(cliente, cabecalho_chefe):
    """RN-11: horário com fuso, campo extra e dados fora da regra dão 422, na criação e no PATCH."""
    com_fuso = nova_eleicao(cliente, cabecalho_chefe, horario_abertura="08:00-03:00")
    extra = nova_eleicao(cliente, cabecalho_chefe, status="ABERTA")
    passado = nova_eleicao(cliente, cabecalho_chefe, data="2026-11-24")
    janela = nova_eleicao(cliente, cabecalho_chefe, horario_abertura="18:00")
    turno = nova_eleicao(cliente, cabecalho_chefe, turno=3)

    assert com_fuso.status_code == 422
    assert extra.status_code == 422
    assert extra.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert (passado.status_code, passado.json()["erro"]["codigo"]) == (422, "DATA_NO_PASSADO")
    assert (janela.status_code, janela.json()["erro"]["codigo"]) == (422, "JANELA_INVALIDA")
    assert (turno.status_code, turno.json()["erro"]["codigo"]) == (422, "DADOS_INVALIDOS")

    # O PATCH só aceita os 5 campos agendáveis; id inexistente → 404 `ELEICAO_NAO_ENCONTRADA`.
    nova_eleicao(cliente, cabecalho_chefe)
    campo_extra = cliente.patch(f"{ELEICOES}/1", json={"status": "ABERTA"}, headers=cabecalho_chefe)
    inexistente = cliente.patch(f"{ELEICOES}/99", json={"turno": 2}, headers=cabecalho_chefe)
    assert campo_extra.status_code == 422
    assert (inexistente.status_code, inexistente.json()["erro"]["codigo"]) == (
        404,
        "ELEICAO_NAO_ENCONTRADA",
    )


def test_mesma_data_e_turno_responde_409_na_criacao_e_na_edicao(cliente, cabecalho_chefe):
    """RN-11 e RN-12: segunda eleição na mesma data e turno → 409 `ELEICAO_DUPLICADA`."""
    assert nova_eleicao(cliente, cabecalho_chefe).status_code == 201

    repetida = nova_eleicao(cliente, cabecalho_chefe)
    segundo_turno = nova_eleicao(cliente, cabecalho_chefe, turno=2)

    assert repetida.status_code == 409
    assert repetida.json()["erro"]["codigo"] == "ELEICAO_DUPLICADA"
    assert segundo_turno.status_code == 201  # outro turno no mesmo dia é permitido

    # A edição passa de novo pelas regras de agendamento.
    janela = cliente.patch(
        f"{ELEICOES}/1", json={"horario_abertura": "17:30"}, headers=cabecalho_chefe
    )
    passado = cliente.patch(f"{ELEICOES}/1", json={"data": "2026-11-01"}, headers=cabecalho_chefe)
    repetida = cliente.patch(f"{ELEICOES}/1", json={"turno": 2}, headers=cabecalho_chefe)
    propria = cliente.patch(f"{ELEICOES}/1", json={"turno": 1}, headers=cabecalho_chefe)
    assert janela.json()["erro"]["codigo"] == "JANELA_INVALIDA"
    assert passado.json()["erro"]["codigo"] == "DATA_NO_PASSADO"
    assert (repetida.status_code, repetida.json()["erro"]["codigo"]) == (409, "ELEICAO_DUPLICADA")
    assert propria.status_code == 200  # a própria eleição é ignorada na checagem de duplicidade


def test_chefe_edita_so_a_eleicao_agendada(cliente, cabecalho_chefe):
    """RN-14: editar uma AGENDADA mexe só no que veio; depois de aberta, o PATCH dá 409."""
    nova_eleicao(cliente, cabecalho_chefe)

    resposta = cliente.patch(
        f"{ELEICOES}/1",
        json={"descricao": "  Nova descrição ", "horario_encerramento": "18:30"},
        headers=cabecalho_chefe,
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["descricao"] == "Nova descrição"
    assert corpo["horario_encerramento"] == "18:30:00"
    assert corpo["horario_abertura"] == "08:00:00"
    assert corpo["turno"] == 1
    assert corpo["status"] == "AGENDADA"

    nova_candidatura(cliente, cabecalho_chefe)
    assert cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe).status_code == 200
    aberta = cliente.patch(
        f"{ELEICOES}/1", json={"horario_encerramento": "18:00"}, headers=cabecalho_chefe
    )

    assert aberta.status_code == 409
    assert aberta.json()["erro"]["codigo"] == "ELEICAO_NAO_EDITAVEL"
    consulta = cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()
    assert consulta["horario_encerramento"] == "18:30:00"


def test_ciclo_de_vida_abrir_encerrar_e_nao_reabrir(cliente, cabecalho_chefe, relogio):
    """RN-13, RN-15 e RN-18: AGENDADA → ABERTA → ENCERRADA, sem voltar; encerra a qualquer hora."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_candidatura(cliente, cabecalho_chefe)

    aberta = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert aberta.status_code == 200, aberta.text
    corpo = aberta.json()
    assert corpo["status"] == "ABERTA"
    assert instante(corpo["aberta_em"]) == datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
    assert corpo["encerrada_em"] is None
    assert rels(corpo) == ["self", "candidaturas", "encerrar", "apuracao-parcial"]

    relogio.avancar(hours=9)  # 19:00, depois do horário previsto
    encerrada = cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)
    reabrir = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)
    encerrar_de_novo = cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)

    assert encerrada.status_code == 200, encerrada.text
    corpo = encerrada.json()
    assert corpo["status"] == "ENCERRADA"
    assert instante(corpo["aberta_em"]) == datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
    assert instante(corpo["encerrada_em"]) == datetime(2026, 11, 25, 19, 0, tzinfo=FUSO)
    assert rels(corpo) == ["self", "candidaturas", "resultado"]
    for resposta in (reabrir, encerrar_de_novo):
        assert resposta.status_code == 409
        assert resposta.json()["erro"]["codigo"] == "TRANSICAO_INVALIDA"
        assert resposta.json()["erro"]["detalhes"] == {"status": "ENCERRADA"}


def test_abertura_recusada_sem_candidaturas_fora_da_janela_ou_da_data(
    cliente, cabecalho_chefe, relogio
):
    """RN-15: sem candidaturas → `SEM_CANDIDATURAS`; fora das 08:00 às 17:00 ou do dia → 409."""
    nova_eleicao(cliente, cabecalho_chefe)

    sem_candidaturas = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert sem_candidaturas.status_code == 409
    assert sem_candidaturas.json()["erro"]["codigo"] == "SEM_CANDIDATURAS"
    assert cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()["status"] == "AGENDADA"

    nova_candidatura(cliente, cabecalho_chefe)
    relogio.avancar(hours=-3)  # 07:00
    antes = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)
    relogio.avancar(hours=10)  # 17:00, exatamente o encerramento
    depois = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert (antes.status_code, antes.json()["erro"]["codigo"]) == (409, "FORA_DA_JANELA")
    assert (depois.status_code, depois.json()["erro"]["codigo"]) == (409, "FORA_DA_JANELA")

    relogio.avancar(hours=17)  # 10:00 do dia seguinte: dentro do horário, mas fora da data
    outro_dia = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert (outro_dia.status_code, outro_dia.json()["erro"]["codigo"]) == (409, "FORA_DA_DATA")
    assert cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()["status"] == "AGENDADA"


def test_segundo_turno_so_abre_com_duas_candidaturas_por_cargo(cliente, cabecalho_chefe):
    """RN-17: no 2º turno, um só candidato no cargo dá 409 `SEGUNDO_TURNO_INCOMPLETO`."""
    eleicao = nova_eleicao(cliente, cabecalho_chefe, turno=2).json()["id"]
    assert nova_candidatura(cliente, cabecalho_chefe, eleicao, numero="10").status_code == 201

    incompleta = cliente.post(f"{ELEICOES}/{eleicao}/abertura", headers=cabecalho_chefe)

    assert incompleta.status_code == 409
    assert incompleta.json()["erro"]["codigo"] == "SEGUNDO_TURNO_INCOMPLETO"
    assert nova_candidatura(cliente, cabecalho_chefe, eleicao, numero="20").status_code == 201
    completa = cliente.post(f"{ELEICOES}/{eleicao}/abertura", headers=cabecalho_chefe)
    assert completa.status_code == 200, completa.text


def test_so_uma_eleicao_aberta_por_vez(cliente, cabecalho_chefe):
    """RN-16: com uma eleição ABERTA, abrir outra → 409; encerrada a primeira, a segunda abre."""
    eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="10")
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="20")

    resposta = cliente.post(f"{ELEICOES}/2/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "OUTRA_ELEICAO_ABERTA"
    assert cliente.get(f"{ELEICOES}/2", headers=cabecalho_chefe).json()["status"] == "AGENDADA"

    cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)
    depois = cliente.post(f"{ELEICOES}/2/abertura", headers=cabecalho_chefe)

    assert depois.status_code == 200, depois.text


def test_qualquer_perfil_consulta_a_eleicao_e_recebe_os_proprios_links(
    cliente, cabecalho_chefe, cabecalho_eleitor, cabecalho_candidato
):
    """RN-19: o Eleitor só recebe `self`; o Chefe recebe as ações; a listagem filtra por status."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    marcar_encerrada(2)

    do_eleitor = cliente.get(f"{ELEICOES}/1", headers=cabecalho_eleitor)
    do_chefe = cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe)

    assert do_eleitor.status_code == 200
    assert rels(do_eleitor.json()) == ["self"]
    assert "abrir" in rels(do_chefe.json())

    inexistente = cliente.get(f"{ELEICOES}/99", headers=cabecalho_chefe)
    assert (inexistente.status_code, inexistente.json()["erro"]["codigo"]) == (
        404,
        "ELEICAO_NAO_ENCONTRADA",
    )
    assert cliente.get(f"{ELEICOES}/0", headers=cabecalho_chefe).status_code == 422

    todas = cliente.get(ELEICOES, headers=cabecalho_candidato).json()
    agendadas = cliente.get(f"{ELEICOES}?status=AGENDADA", headers=cabecalho_chefe).json()
    encerradas = cliente.get(f"{ELEICOES}?status=ENCERRADA", headers=cabecalho_chefe).json()
    abertas = cliente.get(f"{ELEICOES}?status=ABERTA", headers=cabecalho_chefe).json()
    invalida = cliente.get(f"{ELEICOES}?status=QUALQUER", headers=cabecalho_chefe)
    assert [e["id"] for e in todas] == [1, 2]
    assert [e["id"] for e in agendadas] == [1]
    assert [e["id"] for e in encerradas] == [2]
    assert rels(encerradas[0]) == ["self", "candidaturas", "resultado"]  # visão do Chefe
    assert abertas == []
    assert invalida.status_code == 422
    assert invalida.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
