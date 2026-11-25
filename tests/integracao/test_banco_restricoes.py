"""TI-63 a TI-68: restrições e trigger do banco, provocados com SQL direto.

Aqui não passa pela API nem pelo serviço: o objetivo é provar que, mesmo com um bug na
aplicação (ou um `UPDATE` manual), o banco recusa o dado errado. Cada teste confere o nome da
restrição violada, ou a mensagem do trigger.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.database import SessionLocal

MENSAGEM_DO_TRIGGER = "Votos e registros de votação confirmados são imutáveis"
CRIADO_EM = datetime(2026, 11, 1, 9, 0).astimezone()


@pytest.fixture
def sessao():
    with SessionLocal() as sessao_de_teste:
        yield sessao_de_teste


def inserir(sessao, sql: str, **parametros) -> int | None:
    """Executa um INSERT com parâmetros e devolve o `id` gerado (quando há `RETURNING id`)."""
    return sessao.execute(text(sql), parametros).scalar()


def inserir_eleicao(sessao, data: str, turno: int = 1, aberta: bool = False) -> int:
    return inserir(
        sessao,
        "INSERT INTO eleicoes (descricao, data, turno, horario_abertura, horario_encerramento,"
        " status, aberta_em, criado_em) VALUES ('Eleição de teste', :data, :turno, '08:00',"
        " '17:00', :status, :aberta_em, :criado_em) RETURNING id",
        data=data,
        turno=turno,
        status="ABERTA" if aberta else "AGENDADA",
        aberta_em=CRIADO_EM if aberta else None,
        criado_em=CRIADO_EM,
    )


def inserir_candidatura(sessao, eleicao_id: int, cargo: str, numero: str, sufixo: int) -> int:
    """Cria usuário, candidato e partido novos (nomes únicos pelo `sufixo`) e a candidatura."""
    usuario_id = inserir(
        sessao,
        "INSERT INTO usuarios (cpf, nome, senha_hash, perfil, criado_em, atualizado_em)"
        " VALUES (:cpf, 'Candidato de Teste', :hash, 'CANDIDATO', :agora, :agora) RETURNING id",
        cpf=f"{sufixo:011d}",
        hash="x" * 60,
        agora=CRIADO_EM,
    )
    candidato_id = inserir(
        sessao,
        "INSERT INTO candidatos (usuario_id, nome_urna, data_nascimento, criado_em)"
        " VALUES (:usuario_id, 'Fulano', '1970-01-01', :agora) RETURNING id",
        usuario_id=usuario_id,
        agora=CRIADO_EM,
    )
    partido_id = inserir(
        sessao,
        "INSERT INTO partidos (sigla, nome, numero, criado_em)"
        " VALUES (:sigla, :nome, :numero, :agora) RETURNING id",
        sigla=f"P{sufixo}",
        nome=f"Partido {sufixo}",
        numero=10 + sufixo,
        agora=CRIADO_EM,
    )
    return inserir(
        sessao,
        "INSERT INTO candidaturas (eleicao_id, candidato_id, partido_id, cargo, numero, criado_em)"
        " VALUES (:eleicao_id, :candidato_id, :partido_id, :cargo, :numero, :agora) RETURNING id",
        eleicao_id=eleicao_id,
        candidato_id=candidato_id,
        partido_id=partido_id,
        cargo=cargo,
        numero=numero,
        agora=CRIADO_EM,
    )


def inserir_eleitor(sessao) -> int:
    usuario_id = inserir(
        sessao,
        "INSERT INTO usuarios (cpf, nome, senha_hash, perfil, criado_em, atualizado_em)"
        " VALUES ('99999999999', 'Eleitor de Teste', :hash, 'ELEITOR', :agora, :agora)"
        " RETURNING id",
        hash="x" * 60,
        agora=CRIADO_EM,
    )
    return inserir(
        sessao,
        "INSERT INTO eleitores (usuario_id, titulo_eleitor, data_nascimento, criado_em)"
        " VALUES (:usuario_id, '123456789012', '1990-01-01', :agora) RETURNING id",
        usuario_id=usuario_id,
        agora=CRIADO_EM,
    )


def inserir_voto(sessao, eleicao_id: int, cargo: str, tipo: str, candidatura_id: int | None):
    sessao.execute(
        text(
            "INSERT INTO votos (id, eleicao_id, cargo, tipo, candidatura_id)"
            " VALUES (:id, :eleicao_id, :cargo, :tipo, :candidatura_id)"
        ),
        {
            "id": uuid.uuid4(),
            "eleicao_id": eleicao_id,
            "cargo": cargo,
            "tipo": tipo,
            "candidatura_id": candidatura_id,
        },
    )


def inserir_registro(sessao, eleitor_id: int, eleicao_id: int, cargo: str):
    sessao.execute(
        text(
            "INSERT INTO registros_votacao (eleitor_id, eleicao_id, cargo)"
            " VALUES (:eleitor_id, :eleicao_id, :cargo)"
        ),
        {"eleitor_id": eleitor_id, "eleicao_id": eleicao_id, "cargo": cargo},
    )


def nome_da_restricao(erro: IntegrityError) -> str:
    return erro.value.orig.diag.constraint_name


def test_ti63_update_direto_em_votos_e_barrado_pelo_trigger(sessao):
    """TI-63 / RN-59: `UPDATE` direto em `votos` dispara o trigger de imutabilidade."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    inserir_voto(sessao, eleicao_id, "PRESIDENTE", "BRANCO", None)
    sessao.commit()

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(text("UPDATE votos SET tipo = 'NULO'"))
    assert MENSAGEM_DO_TRIGGER in str(erro.value.orig)
    sessao.rollback()

    assert sessao.execute(text("SELECT tipo FROM votos")).scalar() == "BRANCO"


def test_ti63_update_direto_em_registros_votacao_e_barrado_pelo_trigger(sessao):
    """TI-63 / RN-59: o `UPDATE` em `registros_votacao` também é barrado."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    eleitor_id = inserir_eleitor(sessao)
    inserir_registro(sessao, eleitor_id, eleicao_id, "PRESIDENTE")
    sessao.commit()

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(text("UPDATE registros_votacao SET cargo = 'SENADOR'"))
    assert MENSAGEM_DO_TRIGGER in str(erro.value.orig)
    sessao.rollback()


def test_ti64_delete_direto_em_votos_e_registros_e_barrado_pelo_trigger(sessao):
    """TI-64 / RN-59: `DELETE` direto em `votos` e em `registros_votacao` dispara o trigger."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    eleitor_id = inserir_eleitor(sessao)
    inserir_voto(sessao, eleicao_id, "PRESIDENTE", "BRANCO", None)
    inserir_registro(sessao, eleitor_id, eleicao_id, "PRESIDENTE")
    sessao.commit()

    for tabela in ("votos", "registros_votacao"):
        with pytest.raises(DBAPIError) as erro:
            sessao.execute(text(f"DELETE FROM {tabela}"))  # nome fixo do teste, não do usuário
        assert MENSAGEM_DO_TRIGGER in str(erro.value.orig)
        sessao.rollback()

    assert sessao.execute(text("SELECT count(*) FROM votos")).scalar() == 1
    assert sessao.execute(text("SELECT count(*) FROM registros_votacao")).scalar() == 1


def test_ti65_registro_duplicado_viola_a_chave_primaria(sessao):
    """TI-65 / RN-54: o mesmo eleitor, eleição e cargo duas vezes viola `pk_registros_votacao`."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    eleitor_id = inserir_eleitor(sessao)
    inserir_registro(sessao, eleitor_id, eleicao_id, "PRESIDENTE")
    sessao.commit()

    with pytest.raises(IntegrityError) as erro:
        inserir_registro(sessao, eleitor_id, eleicao_id, "PRESIDENTE")
    assert nome_da_restricao(erro) == "pk_registros_votacao"
    sessao.rollback()

    # Outro cargo do mesmo eleitor na mesma eleição é permitido.
    inserir_registro(sessao, eleitor_id, eleicao_id, "SENADOR")
    sessao.commit()


def test_ti65_excluir_eleitor_que_votou_viola_a_fk_do_registro(sessao):
    """TI-65: o nome real da FK é o que `excluir_eleitor` espera (EXCLUSAO_BLOQUEADA)."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    eleitor_id = inserir_eleitor(sessao)
    inserir_registro(sessao, eleitor_id, eleicao_id, "PRESIDENTE")
    sessao.commit()

    with pytest.raises(IntegrityError) as erro:
        sessao.execute(text("DELETE FROM eleitores WHERE id = :id"), {"id": eleitor_id})
    assert nome_da_restricao(erro) == "fk_registros_votacao_eleitor_id_eleitores"
    sessao.rollback()


def test_ti66_duas_eleicoes_abertas_violam_o_indice_parcial(sessao):
    """TI-66 / RN-16: a segunda eleição ABERTA viola `uq_eleicoes_uma_aberta`."""
    inserir_eleicao(sessao, "2026-11-25", aberta=True)
    sessao.commit()

    with pytest.raises(IntegrityError) as erro:
        inserir_eleicao(sessao, "2026-11-26", aberta=True)
    assert nome_da_restricao(erro) == "uq_eleicoes_uma_aberta"
    sessao.rollback()

    # Uma eleição AGENDADA ao lado da aberta é permitida.
    inserir_eleicao(sessao, "2026-11-26")
    sessao.commit()


def test_ti67_voto_nominal_sem_candidatura_viola_o_check(sessao):
    """TI-67 / RN-60: NOMINAL exige candidatura, e BRANCO ou NULO não podem ter."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    candidatura_id = inserir_candidatura(sessao, eleicao_id, "PRESIDENTE", "13", 1)
    sessao.commit()

    with pytest.raises(IntegrityError) as erro:
        inserir_voto(sessao, eleicao_id, "PRESIDENTE", "NOMINAL", None)
    assert nome_da_restricao(erro) == "ck_votos_nominal_tem_candidatura"
    sessao.rollback()

    with pytest.raises(IntegrityError) as erro:
        inserir_voto(sessao, eleicao_id, "PRESIDENTE", "BRANCO", candidatura_id)
    assert nome_da_restricao(erro) == "ck_votos_nominal_tem_candidatura"
    sessao.rollback()


def test_ti67_voto_para_senador_apontando_candidatura_a_presidente_viola_a_fk_composta(sessao):
    """TI-67 / RN-60: a FK composta (id, eleicao_id, cargo) liga o voto ao cargo certo."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    outra_eleicao_id = inserir_eleicao(sessao, "2026-11-26")
    presidente_id = inserir_candidatura(sessao, eleicao_id, "PRESIDENTE", "13", 1)
    sessao.commit()

    with pytest.raises(IntegrityError) as erro:
        inserir_voto(sessao, eleicao_id, "SENADOR", "NOMINAL", presidente_id)
    assert nome_da_restricao(erro) == "fk_votos_candidatura_id_candidaturas"
    sessao.rollback()

    with pytest.raises(IntegrityError) as erro:
        inserir_voto(sessao, outra_eleicao_id, "PRESIDENTE", "NOMINAL", presidente_id)
    assert nome_da_restricao(erro) == "fk_votos_candidatura_id_candidaturas"
    sessao.rollback()

    # O voto certo (mesmo cargo, mesma eleição) é aceito, e BRANCO/NULO dispensam a FK.
    inserir_voto(sessao, eleicao_id, "PRESIDENTE", "NOMINAL", presidente_id)
    inserir_voto(sessao, eleicao_id, "SENADOR", "BRANCO", None)
    inserir_voto(sessao, eleicao_id, "SENADOR", "NULO", None)
    sessao.commit()


def test_ti68_numero_com_digitos_errados_viola_o_check(sessao):
    """TI-68 / RN-42: número que não é de 2 dígitos para Presidente (ou 3 para Senador)."""
    eleicao_id = inserir_eleicao(sessao, "2026-11-25")
    sessao.commit()
    casos = [("PRESIDENTE", "1"), ("PRESIDENTE", "013"), ("PRESIDENTE", "01"), ("SENADOR", "13")]
    for sufixo, (cargo, numero) in enumerate(casos, start=1):
        with pytest.raises(IntegrityError) as erro:
            inserir_candidatura(sessao, eleicao_id, cargo, numero, sufixo)
        assert nome_da_restricao(erro) == "ck_candidaturas_numero_por_cargo"
        sessao.rollback()
