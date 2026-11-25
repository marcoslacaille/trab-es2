"""Exporta a especificação OpenAPI para `docs/openapi.json`.

Uso: `python -m app.scripts.exportar_openapi`. O arquivo alimenta o Swagger UI estático do
GitHub Pages (`docs/index.html`); o TA-03 falha se ele ficar diferente da especificação do código.
"""

import json
from pathlib import Path

from app.main import app

CAMINHO_OPENAPI = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def exportar() -> Path:
    """Grava `app.openapi()` em `docs/openapi.json` (UTF-8, indentado) e devolve o caminho."""
    CAMINHO_OPENAPI.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return CAMINHO_OPENAPI


if __name__ == "__main__":
    print(f"Especificação gravada em {exportar()}")
