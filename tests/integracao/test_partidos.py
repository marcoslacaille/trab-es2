from tests.auxiliares import novo_partido

ROTA_PARTIDOS = "/api/v1/partidos"


def _codigo(resposta) -> str:
    return resposta.json()["erro"]["codigo"]


def test_criar_partido_grava_a_sigla_em_maiusculas(cliente, cabecalho_chefe):
    """RN-32: a sigla digitada em minúsculas é gravada em maiúsculas, e o nome sem os espaços
    das pontas."""
    resposta = novo_partido(
        cliente, cabecalho_chefe, sigla="pino", nome="  Partido da Inovação  ", numero=10
    )

    assert resposta.status_code == 201
    assert resposta.json() == {
        "id": 1,
        "sigla": "PINO",
        "nome": "Partido da Inovação",
        "numero": 10,
    }


def test_partido_repetido_responde_409(cliente, cabecalho_chefe):
    """RN-32: sigla (mesmo em outra caixa), número ou nome já usados dão 409 PARTIDO_DUPLICADO."""
    casos = [
        ({"sigla": "PINO"}, {"sigla": "pino"}),
        ({"numero": 13}, {"numero": 13}),
        ({"nome": "Partido Unico"}, {"nome": "Partido Unico"}),
    ]

    for primeiro, repetido in casos:
        assert novo_partido(cliente, cabecalho_chefe, **primeiro).status_code == 201, primeiro

        resposta = novo_partido(cliente, cabecalho_chefe, **repetido)

        assert resposta.status_code == 409, repetido
        assert _codigo(resposta) == "PARTIDO_DUPLICADO", repetido


def test_lista_partidos_por_numero_para_qualquer_perfil(
    cliente, cabecalho_chefe, cabecalho_eleitor, cabecalho_candidato
):
    """RN-30: eleitor, candidato e Chefe listam os partidos, ordenados por número."""
    novo_partido(cliente, cabecalho_chefe, sigla="BB", numero=30)
    novo_partido(cliente, cabecalho_chefe, sigla="AA", numero=20)

    for cabecalho in (cabecalho_eleitor, cabecalho_candidato, cabecalho_chefe):
        resposta = cliente.get(ROTA_PARTIDOS, headers=cabecalho)

        assert resposta.status_code == 200
        assert [partido["sigla"] for partido in resposta.json()] == ["AA", "BB"]
