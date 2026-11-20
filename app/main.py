from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.compartilhado.banco import obter_sessao

app = FastAPI(
    title="API de Simulação de Eleição Eletrônica",
    version="1.0.0",
)


@app.get("/health", tags=["Sistema"], summary="Verifica se a API e o banco estão no ar")
def health(sessao: Annotated[Session, Depends(obter_sessao)]) -> dict:
    """Executa `SELECT 1` no banco. Responde 200 com `{"status": "ok"}` se tudo estiver no ar."""
    sessao.execute(text("SELECT 1"))
    return {"status": "ok"}
