"""Registro dos modelos ORM.

Importa os modelos de todos os módulos de domínio. O Alembic importa este arquivo para
enxergar todas as tabelas em `Base.metadata`. Cada módulo novo entra aqui.
"""

import app.candidatos.model  # noqa: F401
import app.eleicoes.model  # noqa: F401
import app.eleitores.model  # noqa: F401
import app.identidade.model  # noqa: F401
import app.votacao.model  # noqa: F401
