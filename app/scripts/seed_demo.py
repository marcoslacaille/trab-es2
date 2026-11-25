"""Cria os dados de demonstração. Uso: `python -m app.scripts.seed_demo`.

Usa os serviços dos módulos (nunca SQL direto), então todas as regras de negócio valem
também aqui. As senhas são fixas e públicas: este script é só para a demonstração.
"""

import sys
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.exceptions import ConflitoDeEstado, ErroDeNegocio
from app.core.relogio import agora
from app.dto.candidato_dto import NovoCandidatoDados
from app.dto.candidatura_dto import NovaCandidaturaDados
from app.dto.eleicao_dto import NovaEleicaoDados
from app.dto.eleitor_dto import NovoEleitorDados
from app.dto.partido_dto import NovoPartidoDados
from app.models.enums import Cargo, Perfil
from app.services.candidato_service import CandidatoService
from app.services.eleicao_service import EleicaoService
from app.services.eleitor_service import EleitorService
from app.services.partido_service import PartidoService
from app.services.usuario_service import UsuarioService

CHEFE_CPF = "291.417.776-38"
CHEFE_NOME = "Chefe da Seção"
CHEFE_SENHA = "Chefe@2026"
SENHA_ELEITORES = "Eleitor@123"
SENHA_CANDIDATOS = "Candidato@123"

# (sigla, nome, número)
PARTIDOS = [
    ("PINO", "Partido da Inovação", 10),
    ("UC", "União Cidadã", 20),
    ("MV", "Movimento Verde", 30),
]

# (nome, CPF, título, nascimento)
ELEITORES = [
    ("Ana Beatriz Souza", "011.524.493-03", "100000000001", date(1990, 4, 12)),
    ("Bruno Almeida", "341.672.110-17", "100000000002", date(1985, 9, 30)),
    ("Camila Rocha", "945.807.302-24", "100000000003", date(2001, 1, 15)),
    ("Diego Martins", "917.400.297-04", "100000000004", date(1978, 6, 22)),
    ("Elisa Ferreira", "526.018.159-06", "100000000005", date(2008, 2, 10)),
    ("Fábio Nunes", "356.230.123-53", "100000000006", date(1960, 12, 3)),
]

# (cargo, número, nome de urna, nome completo, CPF, nascimento, sigla do partido)
CANDIDATOS = [
    (
        Cargo.PRESIDENTE,
        "10",
        "Carlos Lima",
        "Carlos Henrique Lima",
        "398.259.791-94",
        date(1968, 3, 5),
        "PINO",
    ),
    (
        Cargo.PRESIDENTE,
        "20",
        "Marina Costa",
        "Marina Costa Ribeiro",
        "795.422.058-30",
        date(1972, 7, 19),
        "UC",
    ),
    (
        Cargo.GOVERNADOR,
        "10",
        "Ricardo Souza",
        "Ricardo Souza Neto",
        "906.790.377-99",
        date(1965, 11, 11),
        "PINO",
    ),
    (
        Cargo.GOVERNADOR,
        "30",
        "Helena Prado",
        "Helena Prado Antunes",
        "787.789.328-07",
        date(1975, 5, 2),
        "MV",
    ),
    (
        Cargo.SENADOR,
        "202",
        "Paulo Mendes",
        "Paulo Roberto Mendes",
        "748.526.057-00",
        date(1959, 8, 8),
        "UC",
    ),
    (
        Cargo.SENADOR,
        "303",
        "Lúcia Ramos",
        "Lúcia Ramos Vieira",
        "442.323.221-91",
        date(1970, 10, 10),
        "MV",
    ),
    (
        Cargo.DEPUTADO_FEDERAL,
        "1010",
        "Tiago Freitas",
        "Tiago Freitas Moura",
        "198.344.417-03",
        date(1988, 4, 4),
        "PINO",
    ),
    (
        Cargo.DEPUTADO_FEDERAL,
        "2020",
        "Sandra Oliveira",
        "Sandra Oliveira Lins",
        "308.023.002-78",
        date(1980, 12, 12),
        "UC",
    ),
    (
        Cargo.DEPUTADO_ESTADUAL,
        "10100",
        "Rafael Dias",
        "Rafael Dias Correia",
        "577.463.706-91",
        date(1992, 3, 14),
        "PINO",
    ),
    (
        Cargo.DEPUTADO_ESTADUAL,
        "30300",
        "Juliana Torres",
        "Juliana Torres Bastos",
        "864.542.841-58",
        date(1983, 7, 7),
        "MV",
    ),
]


def semear() -> int:
    """Cria o cenário completo da demonstração e devolve o código de saída do script.

    0: cenário criado. 1: já havia dados (algum partido), nada foi alterado. 2: uma regra de
    negócio impediu o cenário (por exemplo, já existe eleição de 1º turno hoje); nada foi gravado.
    O cenário é atômico: os serviços fazem o próprio commit, mas aqui cada commit vira só
    um savepoint de uma transação externa, confirmada no fim ou desfeita por inteiro. O Chefe é
    criado só se ainda não existir (o `criar_chefe` pode tê-lo criado antes, com o mesmo CPF).
    """
    momento = agora()
    with engine.connect() as conexao:
        transacao = conexao.begin()
        with Session(
            bind=conexao,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        ) as sessao:
            if PartidoService(sessao).listar_partidos():
                transacao.rollback()
                print("Dados de demonstração já existem; nada foi alterado.")
                print("Para recomeçar: docker compose down -v, up -d e alembic upgrade head.")
                return 1
            try:
                eleicao_id = _criar_cenario(sessao, momento)
            except ErroDeNegocio as erro:
                transacao.rollback()
                print(f"Não foi possível criar a demonstração: {erro.mensagem} ({erro.codigo}).")
                print("Nada foi gravado.")
                return 2
        transacao.commit()  # outro erro sai sem commit: fechar a conexão desfaz tudo
    _imprimir_logins(eleicao_id)
    return 0


def _criar_cenario(sessao: Session, momento: datetime) -> int:
    """Grava Chefe, partidos, eleitores, eleição e candidaturas. Devolve o id da eleição."""
    _criar_chefe_se_preciso(sessao, momento)
    partidos = PartidoService(sessao)
    eleitores = EleitorService(sessao)
    candidatos = CandidatoService(sessao)
    eleicoes = EleicaoService(sessao)

    partido_por_sigla = {}
    for sigla, nome, numero in PARTIDOS:
        partido = partidos.criar_partido(
            NovoPartidoDados(sigla=sigla, nome=nome, numero=numero), momento
        )
        partido_por_sigla[sigla] = partido.id

    for nome, cpf, titulo, nascimento in ELEITORES:
        eleitores.cadastrar_eleitor(
            NovoEleitorDados(
                nome=nome,
                cpf=cpf,
                titulo_eleitor=titulo,
                data_nascimento=nascimento,
                senha=SENHA_ELEITORES,
            ),
            momento,
        )

    eleicao = eleicoes.criar_eleicao(
        NovaEleicaoDados(
            descricao="Eleições Gerais 2026 — 1º turno (simulação)",
            data=momento.date(),
            turno=1,
            horario_abertura=time(0, 0),
            horario_encerramento=time(23, 59),
        ),
        momento,
    )

    for cargo, numero, nome_urna, nome, cpf, nascimento, sigla in CANDIDATOS:
        candidato = candidatos.cadastrar_candidato(
            NovoCandidatoDados(
                nome=nome,
                nome_urna=nome_urna,
                cpf=cpf,
                data_nascimento=nascimento,
                senha=SENHA_CANDIDATOS,
            ),
            momento,
        )
        eleicoes.criar_candidatura(
            eleicao.id,
            NovaCandidaturaDados(
                candidato_id=candidato.id,
                partido_id=partido_por_sigla[sigla],
                cargo=cargo,
                numero=numero,
            ),
            momento,
        )
    return eleicao.id


def _criar_chefe_se_preciso(sessao, momento) -> None:
    """Cria o Chefe da Seção da demonstração, a menos que o CPF já exista."""
    try:
        UsuarioService(sessao).criar_credencial(
            CHEFE_CPF, CHEFE_NOME, CHEFE_SENHA, Perfil.CHEFE_SECAO, momento
        )
    except ConflitoDeEstado as erro:
        if erro.codigo != "CPF_JA_CADASTRADO":
            raise
        return
    sessao.commit()


def _imprimir_logins(eleicao_id: int) -> None:
    """Mostra a tabela de logins da demonstração (senhas fixas: nunca use em produção)."""
    print(f"Dados de demonstração criados. Eleição de hoje: id {eleicao_id} (AGENDADA).\n")
    print(f"{'Perfil':<10} {'Nome':<24} {'CPF':<16} Senha")
    print(f"{'Chefe':<10} {CHEFE_NOME:<24} {CHEFE_CPF:<16} {CHEFE_SENHA}")
    for nome, cpf, _, _ in ELEITORES:
        print(f"{'Eleitor':<10} {nome:<24} {cpf:<16} {SENHA_ELEITORES}")
    for _, _, nome_urna, _, cpf, _, _ in CANDIDATOS:
        print(f"{'Candidato':<10} {nome_urna:<24} {cpf:<16} {SENHA_CANDIDATOS}")


if __name__ == "__main__":
    sys.exit(semear())
