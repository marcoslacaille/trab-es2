"""TI-69 a TI-72: sigilo do voto no esquema, nas respostas e nos logs (RN-60)."""

import base64
import logging
import re
import uuid

from sqlalchemy import inspect, text

from app.core.database import SessionLocal, engine
from tests.auxiliares import eleicao_aberta_com_candidatos, votar

BASE = "/api/v1/votacao/eleicoes"
NUMERO_ESCOLHIDO = "202"


def _texto_do_log(registro: logging.LogRecord) -> str:
    """Texto de um registro de log. No log de requisições, sem a duração em ms (D-104)."""
    if registro.name == "eleicao.requisicoes":
        return re.sub(r" \(\d+\.\d ms\)$", "", registro.getMessage())
    return f"{registro.getMessage()} {registro.args}"


def _valores(estrutura) -> list:
    """Todos os valores folha de um JSON, para conferir o conteúdo sem depender do formato."""
    if isinstance(estrutura, dict):
        return [v for valor in estrutura.values() for v in _valores(valor)]
    if isinstance(estrutura, list):
        return [v for item in estrutura for v in _valores(item)]
    return [estrutura]


def _eleicao_com_voto_em_senador(cliente, cabecalho_chefe, cabecalho_eleitor):
    """Cria a eleição e vota em SENADOR 202. Devolve (ids, nome de urna escolhido, confirmação)."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    cedula = cliente.get(f"{BASE}/{ids['eleicao_id']}/cedula", headers=cabecalho_eleitor).json()
    senador = [c for c in cedula["cargos"] if c["cargo"] == "SENADOR"][0]
    nome_escolhido = {c["numero"]: c["nome_urna"] for c in senador["candidatos"]}[NUMERO_ESCOLHIDO]
    confirmacao = votar(cliente, cabecalho_eleitor, ids["eleicao_id"], "SENADOR", NUMERO_ESCOLHIDO)
    assert confirmacao.status_code == 201, confirmacao.text
    return ids, nome_escolhido, confirmacao


def test_ti69_esquema_nao_liga_voto_a_eleitor_nem_guarda_horario():
    """TI-69 / RN-60: `votos` sem eleitor, usuário ou horário; `registros_votacao` sem escolha."""
    inspetor = inspect(engine)

    colunas_votos = {c["name"]: c for c in inspetor.get_columns("votos")}
    assert not {"eleitor_id", "usuario_id"} & set(colunas_votos)
    for coluna in colunas_votos.values():
        assert "TIMESTAMP" not in str(coluna["type"]).upper(), coluna["name"]
        assert "DATE" not in str(coluna["type"]).upper(), coluna["name"]
        assert "TIME" not in str(coluna["type"]).upper(), coluna["name"]
    tabelas_referenciadas = {fk["referred_table"] for fk in inspetor.get_foreign_keys("votos")}
    assert not {"eleitores", "usuarios"} & tabelas_referenciadas

    colunas_registros = {c["name"] for c in inspetor.get_columns("registros_votacao")}
    assert not {"candidatura_id", "tipo"} & colunas_registros


def test_ti70_nenhuma_resposta_revela_a_escolha(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-70 / RN-60: depois de votar, nenhuma resposta traz o número nem o nome escolhido."""
    ids, nome_escolhido, confirmacao = _eleicao_com_voto_em_senador(
        cliente, cabecalho_chefe, cabecalho_eleitor
    )
    respostas = {
        "confirmacao": confirmacao,
        "participacao": cliente.get(
            f"{BASE}/{ids['eleicao_id']}/participacao", headers=cabecalho_eleitor
        ),
        "eleitores/eu": cliente.get("/api/v1/eleitores/eu", headers=cabecalho_eleitor),
        "auth/me": cliente.get("/api/v1/auth/me", headers=cabecalho_eleitor),
    }

    for nome, resposta in respostas.items():
        assert resposta.status_code in (200, 201), (nome, resposta.text)
        assert nome_escolhido not in resposta.text, nome
        assert NUMERO_ESCOLHIDO not in _valores(resposta.json()), nome
        assert "candidatura_id" not in resposta.text, nome
    # Sanidade: a participação diz que votou, mas não em quem.
    cargos = respostas["participacao"].json()["cargos"]
    assert {c["cargo"]: c["ja_votou"] for c in cargos} == {"SENADOR": True, "PRESIDENTE": False}


def test_ti71_ids_dos_votos_sao_uuid_versao_4(cliente, cabecalho_chefe, cabecalho_eleitor):
    """TI-71 / RN-60: o id de cada voto é um UUID aleatório (versão 4)."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    assert votar(cliente, cabecalho_eleitor, ids["eleicao_id"], "SENADOR", "101").status_code == 201
    assert (
        votar(cliente, cabecalho_eleitor, ids["eleicao_id"], "PRESIDENTE", branco=True).status_code
        == 201
    )

    with SessionLocal() as sessao:
        identificadores = sessao.execute(text("SELECT id::text FROM votos")).scalars().all()

    assert len(identificadores) == 2
    for identificador in identificadores:
        assert uuid.UUID(identificador).version == 4


def test_ti72_logs_nao_contem_token_numero_nem_candidatura(
    cliente, cabecalho_chefe, cabecalho_eleitor, caplog
):
    """TI-72 / RN-60: registrar e confirmar o voto não deixa a escolha nos logs (nível DEBUG)."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    eleicao = ids["eleicao_id"]
    candidatura = ids["candidaturas"]["SENADOR"][NUMERO_ESCOLHIDO]

    with caplog.at_level(logging.DEBUG):
        registro = cliente.post(
            f"{BASE}/{eleicao}/votos/registro",
            json={"cargo": "SENADOR", "modo": "NUMERO", "numero": NUMERO_ESCOLHIDO},
            headers=cabecalho_eleitor,
        )
        token = registro.json()["token_cedula"]
        confirmacao = cliente.post(
            f"{BASE}/{eleicao}/votos/confirmacao",
            json={"token_cedula": token},
            headers=cabecalho_eleitor,
        )
    assert confirmacao.status_code == 201, confirmacao.text

    # Junta mensagem formatada e argumentos de cada registro de log.
    # A duração do log de requisições (ex.: "202.4 ms") é só um tempo e pode coincidir com o
    # número do candidato; por isso ela sai do texto conferido (D-104).
    texto = "\n".join(_texto_do_log(r) for r in caplog.records)
    assert token not in texto
    assert NUMERO_ESCOLHIDO not in texto
    assert f"candidatura_id={candidatura}" not in texto
    assert "candidatura_id" not in texto


def test_d144_previa_nao_fica_em_cache_e_a_cedula_e_opaca(
    cliente, cabecalho_chefe, cabecalho_eleitor
):
    """D-144 / RN-60: a prévia vem com `no-store` e o `token_cedula` não revela a escolha."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    resposta = cliente.post(
        f"{BASE}/{ids['eleicao_id']}/votos/registro",
        json={"cargo": "SENADOR", "modo": "NUMERO", "numero": NUMERO_ESCOLHIDO},
        headers=cabecalho_eleitor,
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["cache-control"] == "no-store"
    token = resposta.json()["token_cedula"]
    aberto = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    for revelador in (b"candidatura_id", b"usuario_id", b"SENADOR", b"NOMINAL"):
        assert revelador not in aberto
