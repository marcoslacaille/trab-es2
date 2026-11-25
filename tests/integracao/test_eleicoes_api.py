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
    """Muda o status direto no banco, só para montar o cenário do filtro (TI-17).

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


def test_ti09_chefe_cria_eleicao_agendada_com_link_abrir(cliente, cabecalho_chefe):
    """TI-09 / RN-10, RN-19: criar → 201, AGENDADA, sem carimbos e com o link `abrir`."""
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


def test_ti09_so_o_chefe_cria_eleicao(cliente, cabecalho_eleitor, cabecalho_candidato):
    """RN-10: eleitor e candidato recebem 403 `PERFIL_NAO_AUTORIZADO`; sem token, 401."""
    for cabecalho in (cabecalho_eleitor, cabecalho_candidato):
        resposta = nova_eleicao(cliente, cabecalho)
        assert resposta.status_code == 403
        assert resposta.json()["erro"]["codigo"] == "PERFIL_NAO_AUTORIZADO"

    assert nova_eleicao(cliente, {}).status_code == 401


def test_ti09_recusa_dados_invalidos(cliente, cabecalho_chefe):
    """RN-11: data no passado, janela invertida e turno fora de 1 e 2 dão 422."""
    passado = nova_eleicao(cliente, cabecalho_chefe, data="2026-11-24")
    janela = nova_eleicao(cliente, cabecalho_chefe, horario_abertura="18:00")
    turno = nova_eleicao(cliente, cabecalho_chefe, turno=3)

    assert (passado.status_code, passado.json()["erro"]["codigo"]) == (422, "DATA_NO_PASSADO")
    assert (janela.status_code, janela.json()["erro"]["codigo"]) == (422, "JANELA_INVALIDA")
    assert (turno.status_code, turno.json()["erro"]["codigo"]) == (422, "DADOS_INVALIDOS")


def test_ti09_recusa_horario_com_fuso_e_campo_desconhecido(cliente, cabecalho_chefe):
    """Esquema: horário com fuso e campo extra dão 422 `DADOS_INVALIDOS`."""
    com_fuso = nova_eleicao(cliente, cabecalho_chefe, horario_abertura="08:00-03:00")
    extra = nova_eleicao(cliente, cabecalho_chefe, status="ABERTA")

    assert com_fuso.status_code == 422
    assert extra.status_code == 422
    assert extra.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_ti10_mesma_data_e_turno_da_409(cliente, cabecalho_chefe):
    """TI-10 / RN-12: segunda eleição na mesma data e turno → 409 `ELEICAO_DUPLICADA`."""
    assert nova_eleicao(cliente, cabecalho_chefe).status_code == 201

    repetida = nova_eleicao(cliente, cabecalho_chefe)
    segundo_turno = nova_eleicao(cliente, cabecalho_chefe, turno=2)

    assert repetida.status_code == 409
    assert repetida.json()["erro"]["codigo"] == "ELEICAO_DUPLICADA"
    assert segundo_turno.status_code == 201  # outro turno no mesmo dia é permitido


def test_ti11_chefe_edita_eleicao_agendada(cliente, cabecalho_chefe):
    """TI-11 / RN-14: editar uma AGENDADA funciona e mexe só no que veio."""
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


def test_ti11_editar_eleicao_aberta_da_409(cliente, cabecalho_chefe):
    """TI-11 / RN-14: editar uma eleição ABERTA → 409 `ELEICAO_NAO_EDITAVEL`, sem alterar nada."""
    eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)

    resposta = cliente.patch(
        f"{ELEICOES}/1", json={"horario_encerramento": "18:00"}, headers=cabecalho_chefe
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "ELEICAO_NAO_EDITAVEL"
    assert cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()["horario_encerramento"] == (
        "17:00:00"
    )


def test_ti11_edicao_passa_de_novo_pelas_regras_de_agendamento(cliente, cabecalho_chefe):
    """RN-11 e RN-12 na edição: janela invertida, data passada e data/turno repetidos."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)

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


def test_ti11_edicao_recusa_campo_desconhecido_e_eleicao_inexistente(cliente, cabecalho_chefe):
    """O PATCH só aceita os 5 campos agendáveis; id inexistente → 404 `ELEICAO_NAO_ENCONTRADA`."""
    nova_eleicao(cliente, cabecalho_chefe)

    extra = cliente.patch(f"{ELEICOES}/1", json={"status": "ABERTA"}, headers=cabecalho_chefe)
    inexistente = cliente.patch(f"{ELEICOES}/99", json={"turno": 2}, headers=cabecalho_chefe)

    assert extra.status_code == 422
    assert (inexistente.status_code, inexistente.json()["erro"]["codigo"]) == (
        404,
        "ELEICAO_NAO_ENCONTRADA",
    )


def test_ti11_so_o_chefe_edita(cliente, cabecalho_chefe, cabecalho_eleitor):
    """RN-10: eleitor recebe 403 ao editar."""
    nova_eleicao(cliente, cabecalho_chefe)

    resposta = cliente.patch(f"{ELEICOES}/1", json={"turno": 2}, headers=cabecalho_eleitor)

    assert resposta.status_code == 403


def test_ti12_abrir_na_data_e_janela_deixa_aberta_com_link_encerrar(
    cliente, cabecalho_chefe, relogio
):
    """TI-12 / RN-15: abrir na data e janela → ABERTA, `aberta_em` preenchido, link `encerrar`."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_candidatura(cliente, cabecalho_chefe)

    resposta = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "ABERTA"
    assert instante(corpo["aberta_em"]) == datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
    assert corpo["encerrada_em"] is None
    assert rels(corpo) == ["self", "encerrar", "apuracao-parcial"]


def test_ti12_abre_exatamente_no_horario_de_abertura(cliente, cabecalho_chefe, relogio):
    """RN-15: o horário de abertura é inclusivo (abre às 08:00 em ponto)."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_candidatura(cliente, cabecalho_chefe)
    relogio.avancar(hours=-2)

    resposta = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 200, resposta.text


def test_ti13_abrir_sem_candidaturas_da_409(cliente, cabecalho_chefe):
    """TI-13 / RN-15: abrir na data e na janela, mas sem candidaturas → 409 `SEM_CANDIDATURAS`."""
    nova_eleicao(cliente, cabecalho_chefe)

    resposta = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "SEM_CANDIDATURAS"
    assert cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe).json()["status"] == "AGENDADA"


def test_ti14_abrir_fora_da_data_da_409(cliente, cabecalho_chefe, relogio):
    """TI-14 / RN-15: em outro dia que não o da eleição → 409 `FORA_DA_DATA`."""
    nova_eleicao(cliente, cabecalho_chefe)
    relogio.avancar(days=1)

    resposta = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "FORA_DA_DATA"


def test_ti14_abrir_fora_da_janela_da_409(cliente, cabecalho_chefe, relogio):
    """TI-14 / RN-15: antes das 08:00 e a partir das 17:00 → 409 `FORA_DA_JANELA`."""
    nova_eleicao(cliente, cabecalho_chefe)

    relogio.avancar(hours=-3)  # 07:00
    antes = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)
    relogio.avancar(hours=10)  # 17:00, exatamente o encerramento
    depois = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)

    assert (antes.status_code, antes.json()["erro"]["codigo"]) == (409, "FORA_DA_JANELA")
    assert (depois.status_code, depois.json()["erro"]["codigo"]) == (409, "FORA_DA_JANELA")


def test_ti15_abrir_com_outra_eleicao_aberta_da_409(cliente, cabecalho_chefe):
    """TI-15 / RN-16: com uma eleição ABERTA, abrir outra → 409 `OUTRA_ELEICAO_ABERTA`."""
    eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="10")
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="20")

    resposta = cliente.post(f"{ELEICOES}/2/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "OUTRA_ELEICAO_ABERTA"
    assert cliente.get(f"{ELEICOES}/2", headers=cabecalho_chefe).json()["status"] == "AGENDADA"


def test_ti15_depois_de_encerrar_a_primeira_a_segunda_abre(cliente, cabecalho_chefe):
    """RN-16: a trava é só enquanto há outra ABERTA; encerrada a primeira, a segunda abre."""
    eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="10")
    nova_candidatura(cliente, cabecalho_chefe, eleicao_id=2, numero="20")

    cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)
    resposta = cliente.post(f"{ELEICOES}/2/abertura", headers=cabecalho_chefe)

    assert resposta.status_code == 200, resposta.text


def test_ti16_encerrar_aberta_funciona_e_reabrir_encerrada_da_409(
    cliente, cabecalho_chefe, relogio
):
    """TI-16 / RN-13, RN-18: encerra a ABERTA (a qualquer hora); reabrir a ENCERRADA → 409."""
    eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    relogio.avancar(hours=9)  # 19:00, depois do horário previsto: encerrar vale a qualquer hora

    encerrada = cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)
    reabrir = cliente.post(f"{ELEICOES}/1/abertura", headers=cabecalho_chefe)
    encerrar_de_novo = cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)

    assert encerrada.status_code == 200, encerrada.text
    corpo = encerrada.json()
    assert corpo["status"] == "ENCERRADA"
    assert instante(corpo["aberta_em"]) == datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)
    assert instante(corpo["encerrada_em"]) == datetime(2026, 11, 25, 19, 0, tzinfo=FUSO)
    assert rels(corpo) == ["self", "resultado"]
    for resposta in (reabrir, encerrar_de_novo):
        assert resposta.status_code == 409
        assert resposta.json()["erro"]["codigo"] == "TRANSICAO_INVALIDA"
        assert resposta.json()["erro"]["detalhes"] == {"status": "ENCERRADA"}


def test_abertura_e_encerramento_so_para_o_chefe_e_com_eleicao_existente(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-10: eleitor recebe 403; eleição inexistente → 404 `ELEICAO_NAO_ENCONTRADA`."""
    nova_eleicao(cliente, cabecalho_chefe)

    for rota in ("abertura", "encerramento"):
        assert cliente.post(f"{ELEICOES}/1/{rota}", headers=cabecalho_eleitor).status_code == 403
        inexistente = cliente.post(f"{ELEICOES}/99/{rota}", headers=cabecalho_chefe)
        assert (inexistente.status_code, inexistente.json()["erro"]["codigo"]) == (
            404,
            "ELEICAO_NAO_ENCONTRADA",
        )


def test_encerrar_eleicao_agendada_da_409(cliente, cabecalho_chefe):
    """RN-13 / RN-18: só se encerra uma ABERTA; a AGENDADA responde `TRANSICAO_INVALIDA`."""
    nova_eleicao(cliente, cabecalho_chefe)

    resposta = cliente.post(f"{ELEICOES}/1/encerramento", headers=cabecalho_chefe)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "TRANSICAO_INVALIDA"


def test_qualquer_usuario_consulta_eleicao_e_recebe_links_do_seu_perfil(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """RN-19: o Eleitor consulta a AGENDADA e só recebe `self`; o Chefe recebe as ações."""
    nova_eleicao(cliente, cabecalho_chefe)

    do_eleitor = cliente.get(f"{ELEICOES}/1", headers=cabecalho_eleitor)
    do_chefe = cliente.get(f"{ELEICOES}/1", headers=cabecalho_chefe)

    assert do_eleitor.status_code == 200
    assert rels(do_eleitor.json()) == ["self"]
    assert "abrir" in rels(do_chefe.json())


def test_consultar_eleicao_inexistente_ou_sem_token(cliente, cabecalho_chefe):
    """RN-19: 404 `ELEICAO_NAO_ENCONTRADA` para id inexistente; 401 sem token; 422 para id 0."""
    inexistente = cliente.get(f"{ELEICOES}/99", headers=cabecalho_chefe)

    assert (inexistente.status_code, inexistente.json()["erro"]["codigo"]) == (
        404,
        "ELEICAO_NAO_ENCONTRADA",
    )
    assert cliente.get(f"{ELEICOES}/1").status_code == 401
    assert cliente.get(f"{ELEICOES}/0", headers=cabecalho_chefe).status_code == 422


def test_ti17_lista_eleicoes_com_filtro_de_status(cliente, cabecalho_chefe, cabecalho_candidato):
    """TI-17 / RN-19: lista todas, filtra por status, e status inválido dá 422."""
    nova_eleicao(cliente, cabecalho_chefe)
    nova_eleicao(cliente, cabecalho_chefe, turno=2)
    marcar_encerrada(2)

    todas = cliente.get(ELEICOES, headers=cabecalho_candidato).json()
    agendadas = cliente.get(f"{ELEICOES}?status=AGENDADA", headers=cabecalho_chefe).json()
    encerradas = cliente.get(f"{ELEICOES}?status=ENCERRADA", headers=cabecalho_chefe).json()
    abertas = cliente.get(f"{ELEICOES}?status=ABERTA", headers=cabecalho_chefe).json()
    invalida = cliente.get(f"{ELEICOES}?status=QUALQUER", headers=cabecalho_chefe)

    assert [e["id"] for e in todas] == [1, 2]
    assert [e["id"] for e in agendadas] == [1]
    assert [e["id"] for e in encerradas] == [2]
    assert rels(encerradas[0]) == ["self", "resultado"]
    assert abertas == []
    assert invalida.status_code == 422
    assert invalida.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_listar_eleicoes_exige_login(cliente):
    """RN-06: sem token, a listagem responde 401."""
    assert cliente.get(ELEICOES).status_code == 401
