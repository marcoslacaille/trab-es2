"""Registro dos modelos ORM.

Importa os modelos de todos os módulos de domínio. O Alembic importa este arquivo para
enxergar todas as tabelas em `Base.metadata`. Cada tarefa acrescenta aqui o módulo novo.
"""

import app.candidatos.modelos  # noqa: F401
import app.eleicoes.modelos  # noqa: F401
import app.eleitores.modelos  # noqa: F401
import app.identidade.modelos  # noqa: F401
import app.votacao.modelos  # noqa: F401
