"""Caminhos internos dos serviços que a API normal não alcança (RN-05, RN-08, RN-24, RN-43)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.candidatos import service as service_candidatos
from app.core.database import SessionLocal
from app.core.exceptions import DadosInvalidos, NaoEncontrado
from app.core.relogio import agora
from app.eleicoes import service as service_eleicoes
from app.eleitores import service as service_eleitores
from app.identidade import service as service_identidade
from app.models.enums import Cargo, Perfil
from app.repositories.candidato_repository import CandidatoRepository
from app.repositories.eleitor_repository import EleitorRepository
from app.schemas.eleicao_schema import links_da_eleicao
from tests.auxiliares import (
    SENHA_CANDIDATO,
    SENHA_ELEITOR,
    criar_chefe,
    eleicao_aberta_com_candidatos,
    login,
    novo_candidato,
    novo_eleitor,
)

PREFIXO = "/api/v1"


def _erro_de_integridade_sem_nome() -> IntegrityError:
    """Um `IntegrityError` sem nome de restrição (como o de uma violação que não conhecemos)."""
    return IntegrityError("DELETE ...", {}, Exception("violação desconhecida"))


# ------------------------------------------------------------------ identidade


def test_atualizar_credencial_troca_nome_e_senha():
    """RN-05 e RN-08: nome e senha novos valem no login; o hash anterior deixa de valer."""
    usuario_id = criar_chefe()

    with SessionLocal() as sessao:
        service_identidade.atualizar_credencial(
            sessao, usuario_id, agora(), nome="  Novo Nome  ", senha="NovaSenha@456"
        )
        sessao.commit()

    with SessionLocal() as sessao:
        usuario = service_identidade.obter_usuario(sessao, usuario_id)
        assert usuario is not None and usuario.nome == "Novo Nome"
        assert service_identidade.autenticar(sessao, usuario.cpf, "NovaSenha@456")


def test_atualizar_credencial_recusa_nome_curto_e_senha_fraca():
    """RN-08 e RN-05: nome com menos de 3 caracteres e senha fraca são recusados (422)."""
    usuario_id = criar_chefe()

    with SessionLocal() as sessao:
        with pytest.raises(DadosInvalidos) as nome_curto:
            service_identidade.atualizar_credencial(sessao, usuario_id, agora(), nome=" ab ")
        with pytest.raises(DadosInvalidos) as senha_fraca:
            service_identidade.atualizar_credencial(sessao, usuario_id, agora(), senha="fraca")

    assert nome_curto.value.codigo == "DADOS_INVALIDOS"
    assert senha_fraca.value.codigo == "SENHA_INVALIDA"


def test_credencial_inexistente_e_inconsistencia_interna():
    """Atualizar ou remover credencial que não existe é erro de programação (`LookupError`)."""
    with SessionLocal() as sessao:
        with pytest.raises(LookupError):
            service_identidade.atualizar_credencial(sessao, 999, agora(), nome="Fulano")
        with pytest.raises(LookupError):
            service_identidade.remover_credencial(sessao, 999)


def test_obter_usuarios_com_lista_vazia_e_ids_inexistentes():
    """`obter_usuarios` devolve `{}` sem ids e deixa de fora os ids que não existem."""
    usuario_id = criar_chefe()

    with SessionLocal() as sessao:
        assert service_identidade.obter_usuarios(sessao, []) == {}
        achados = service_identidade.obter_usuarios(sessao, [usuario_id, 999])

    assert list(achados) == [usuario_id]


# ------------------------------------------------------------------ candidatos


def test_alterar_candidato_pela_api_muda_nome_urna_nascimento_nome_e_senha(
    cliente, cabecalho_chefe
):
    """RN-31 e RN-05: o PATCH muda todos os campos permitidos, inclusive a senha de login."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()

    alterado = cliente.patch(
        f"{PREFIXO}/candidatos/{criado['id']}",
        json={
            "nome": "Nome Completo Novo",
            "nome_urna": "Urna Nova",
            "data_nascimento": "1970-01-01",
            "senha": "NovaSenha@456",
        },
        headers=cabecalho_chefe,
    )

    assert alterado.status_code == 200, alterado.text
    corpo = alterado.json()
    assert corpo["nome"] == "Nome Completo Novo" and corpo["nome_urna"] == "Urna Nova"
    assert corpo["data_nascimento"] == "1970-01-01"
    assert login(cliente, criado["cpf"], "NovaSenha@456")
    senha_antiga = cliente.post(
        f"{PREFIXO}/auth/login", data={"username": criado["cpf"], "password": SENHA_CANDIDATO}
    )
    assert senha_antiga.status_code == 401


def test_obter_candidato_logado_sem_candidato_responde_404():
    """RN-30: credencial que não é de candidato não tem `/candidatos/eu`."""
    chefe_id = criar_chefe()

    with SessionLocal() as sessao, pytest.raises(NaoEncontrado) as erro:
        service_candidatos.obter_candidato_logado(sessao, chefe_id)

    assert erro.value.codigo == "CANDIDATO_NAO_ENCONTRADO"


def test_candidato_sem_credencial_e_inconsistencia_interna(cliente, cabecalho_chefe, monkeypatch):
    """Candidato cuja credencial sumiu é inconsistência (`LookupError`, vira 500)."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()
    monkeypatch.setattr(service_identidade, "obter_usuarios", lambda sessao, ids: {})

    with SessionLocal() as sessao, pytest.raises(LookupError):
        service_candidatos.obter_candidato(sessao, criado["id"])


def test_excluir_candidato_repassa_erro_de_integridade_desconhecido(
    cliente, cabecalho_chefe, monkeypatch
):
    """Violação que não é a da candidatura não vira 409: o erro original sobe."""

    def falhar(self, candidato):
        raise _erro_de_integridade_sem_nome()

    criado = novo_candidato(cliente, cabecalho_chefe).json()
    monkeypatch.setattr(CandidatoRepository, "remover_candidato", falhar)

    with SessionLocal() as sessao, pytest.raises(IntegrityError):
        service_candidatos.excluir_candidato(sessao, criado["id"])


# ------------------------------------------------------------------- eleitores


def test_obter_eleitor_do_usuario_sem_eleitor_devolve_none():
    """RN-25: credencial sem eleitor (o Chefe, por exemplo) não tem linha em `eleitores`."""
    chefe_id = criar_chefe()

    with SessionLocal() as sessao:
        assert service_eleitores.obter_eleitor_do_usuario(sessao, chefe_id) is None
        with pytest.raises(NaoEncontrado) as erro:
            service_eleitores.obter_eleitor_logado(sessao, chefe_id)

    assert erro.value.codigo == "ELEITOR_NAO_ENCONTRADO"


def test_eleitor_sem_credencial_e_inconsistencia_interna(cliente, cabecalho_chefe, monkeypatch):
    """Eleitor cuja credencial sumiu é inconsistência (`LookupError`, vira 500)."""
    criado = novo_eleitor(cliente, cabecalho_chefe).json()
    monkeypatch.setattr(service_identidade, "obter_usuarios", lambda sessao, ids: {})

    with SessionLocal() as sessao, pytest.raises(LookupError):
        service_eleitores.obter_eleitor(sessao, criado["id"])


def test_excluir_eleitor_repassa_erro_de_integridade_desconhecido(
    cliente, cabecalho_chefe, monkeypatch
):
    """RN-24: só a violação `fk_registros_votacao_eleitor_id_eleitores` vira 409; outra sobe."""

    def falhar(self, eleitor):
        raise _erro_de_integridade_sem_nome()

    criado = novo_eleitor(cliente, cabecalho_chefe).json()
    monkeypatch.setattr(EleitorRepository, "remover", falhar)

    with SessionLocal() as sessao, pytest.raises(IntegrityError):
        service_eleitores.excluir_eleitor(sessao, criado["id"])


# -------------------------------------------------------------------- eleições


def test_candidaturas_do_usuario_sem_candidato_devolve_lista_vazia():
    """RN-47: quem não é candidato (o Chefe) não tem candidaturas."""
    chefe_id = criar_chefe()

    with SessionLocal() as sessao:
        assert service_eleicoes.candidaturas_do_usuario(sessao, chefe_id) == []


def test_buscar_candidatura_por_numero_acha_ou_devolve_none(cliente, cabecalho_chefe):
    """RN-43: a busca por (eleição, cargo, número) acha a candidatura, ou devolve `None`."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)

    with SessionLocal() as sessao:
        achada = service_eleicoes.buscar_candidatura_por_numero(
            sessao, ids["eleicao_id"], Cargo.SENADOR, "202"
        )
        ausente = service_eleicoes.buscar_candidatura_por_numero(
            sessao, ids["eleicao_id"], Cargo.SENADOR, "999"
        )
        outro_cargo = service_eleicoes.buscar_candidatura_por_numero(
            sessao, ids["eleicao_id"], Cargo.GOVERNADOR, "202"
        )

    assert achada is not None and achada.id == ids["candidaturas"]["SENADOR"]["202"]
    assert ausente is None and outro_cargo is None


def test_links_da_eleicao_aberta_para_perfil_desconhecido(cliente, cabecalho_chefe):
    """RN-19: um perfil fora dos três conhecidos só recebe o link `self`."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)

    with SessionLocal() as sessao:
        eleicao = service_eleicoes.obter_eleicao(sessao, ids["eleicao_id"])

    links = links_da_eleicao(eleicao, "VISITANTE")

    assert [link.rel for link in links] == ["self"]


# --------------------------------------------------------------------- votação


def test_votacao_com_perfil_eleitor_sem_cadastro_responde_404(cliente, cabecalho_chefe):
    """D-087: credencial ELEITOR sem linha em `eleitores` recebe 404 nas 4 rotas de votação."""
    ids = eleicao_aberta_com_candidatos(cliente, cabecalho_chefe)
    eleicao = ids["eleicao_id"]
    with SessionLocal() as sessao:
        service_identidade.criar_credencial(
            sessao, "01152449303", "Sem Cadastro", SENHA_ELEITOR, Perfil.ELEITOR, agora()
        )
        sessao.commit()
    cabecalho = login(cliente, "01152449303", SENHA_ELEITOR)
    base = f"{PREFIXO}/votacao/eleicoes/{eleicao}"

    respostas = [
        cliente.get(f"{base}/cedula", headers=cabecalho),
        cliente.post(
            f"{base}/votos/registro",
            json={"cargo": "PRESIDENTE", "modo": "BRANCO"},
            headers=cabecalho,
        ),
        cliente.post(
            f"{base}/votos/confirmacao", json={"token_cedula": "x" * 20}, headers=cabecalho
        ),
        cliente.get(f"{base}/participacao", headers=cabecalho),
    ]

    assert [r.status_code for r in respostas] == [404, 404, 422, 404]
    assert [r.json()["erro"]["codigo"] for r in respostas] == [
        "ELEITOR_NAO_ENCONTRADO",
        "ELEITOR_NAO_ENCONTRADO",
        "CEDULA_INVALIDA",  # a cédula é lida antes de procurar o eleitor
        "ELEITOR_NAO_ENCONTRADO",
    ]


def test_atualizar_credencial_so_com_nome_mantem_a_senha():
    """RN-08: trocar só o nome não mexe na senha (campo ausente não muda)."""
    usuario_id = criar_chefe()

    with SessionLocal() as sessao:
        service_identidade.atualizar_credencial(sessao, usuario_id, agora(), nome="Outro Nome")
        sessao.commit()

    with SessionLocal() as sessao:
        usuario = service_identidade.obter_usuario(sessao, usuario_id)
        assert usuario is not None and usuario.nome == "Outro Nome"
        assert service_identidade.autenticar(sessao, usuario.cpf, "Chefe@2026")


def test_alterar_candidato_so_com_nome_urna_nao_mexe_na_credencial(cliente, cabecalho_chefe):
    """RN-31: PATCH só com `nome_urna` mantém nome e senha de login."""
    criado = novo_candidato(cliente, cabecalho_chefe).json()

    alterado = cliente.patch(
        f"{PREFIXO}/candidatos/{criado['id']}",
        json={"nome_urna": "So Urna"},
        headers=cabecalho_chefe,
    )

    assert alterado.status_code == 200 and alterado.json()["nome"] == criado["nome"]
    assert login(cliente, criado["cpf"], SENHA_CANDIDATO)
