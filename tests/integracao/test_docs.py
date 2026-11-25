"""O Swagger UI que a própria API serve em `/docs`."""

from app.core.openapi import PARAMETROS_SWAGGER_UI


def test_docs_serve_o_swagger_ui_com_os_parametros_configurados(cliente):
    """O `/docs` responde 200 e a página leva os parâmetros do Swagger UI (ex.: Authorize salvo)."""
    resposta = cliente.get("/docs")

    assert resposta.status_code == 200
    for parametro in PARAMETROS_SWAGGER_UI:
        assert parametro in resposta.text, parametro
