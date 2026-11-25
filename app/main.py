from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.controllers import (
    apuracao_controller,
    auth_controller,
    candidato_controller,
    candidatura_controller,
    eleicao_controller,
    eleitor_controller,
    partido_controller,
    votacao_controller,
)
from app.core.database import obter_sessao
from app.core.exceptions import registrar_tratadores
from app.core.log_requisicoes import registrar_log_de_requisicoes
from app.core.openapi import DESCRICAO_API, TAGS

app = FastAPI(
    title="API de Simulação de Eleição Eletrônica",
    version="1.0.0",
    description=DESCRICAO_API,
    openapi_tags=TAGS,
    # operationId legível no Swagger (ex.: "abrir"); os nomes das funções de rota são únicos.
    generate_unique_id_function=lambda rota: rota.name,
)
registrar_tratadores(app)
registrar_log_de_requisicoes(app)

PREFIXO = "/api/v1"
app.include_router(auth_controller.roteador, prefix=PREFIXO)
app.include_router(eleicao_controller.roteador, prefix=PREFIXO)
app.include_router(candidatura_controller.roteador_candidaturas, prefix=PREFIXO)
app.include_router(eleitor_controller.roteador, prefix=PREFIXO)
app.include_router(candidato_controller.roteador, prefix=PREFIXO)
app.include_router(partido_controller.roteador, prefix=PREFIXO)
app.include_router(votacao_controller.roteador, prefix=PREFIXO)
app.include_router(apuracao_controller.roteador, prefix=PREFIXO)


@app.get("/health", tags=["Sistema"], summary="Verifica se a API e o banco estão no ar")
def health(sessao: Annotated[Session, Depends(obter_sessao)]) -> dict:
    """Executa `SELECT 1` no banco. Responde 200 com `{"status": "ok"}` se tudo estiver no ar."""
    sessao.execute(text("SELECT 1"))
    return {"status": "ok"}
