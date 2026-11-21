"""Log de requisições HTTP: método, caminho, status e duração (RN-60, RN-04).

Nunca registra corpo, cabeçalhos, token, senha nem a query string (ela pode ter nome ou CPF).
Assim o log não revela quem votou nem em quem (RN-60).
"""

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import FastAPI, Request, Response

registro = logging.getLogger("eleicao.requisicoes")

if not registro.handlers:
    # Sob o uvicorn o logger raiz não tem handler; sem este, o INFO não apareceria.
    _saida = logging.StreamHandler()
    _saida.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    registro.addHandler(_saida)
    registro.setLevel(logging.INFO)


def registrar_log_de_requisicoes(app: FastAPI) -> None:
    """Instala o middleware que loga uma linha por requisição, depois da resposta."""

    @app.middleware("http")
    async def logar(
        requisicao: Request, proxima: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inicio = perf_counter()
        status = 500  # se a rota levantar erro sem tratador, o cliente recebe 500
        try:
            resposta = await proxima(requisicao)
            status = resposta.status_code
            return resposta
        finally:
            duracao_ms = (perf_counter() - inicio) * 1000
            registro.info(
                "%s %s -> %s (%.1f ms)", requisicao.method, requisicao.url.path, status, duracao_ms
            )
