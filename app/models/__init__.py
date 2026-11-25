"""Registro dos models: importar `app.models` carrega todas as tabelas em `Base.metadata`.

O Alembic importa este pacote para enxergar as tabelas. Toda entidade nova entra aqui.
"""

import app.models.candidato  # noqa: F401
import app.models.candidatura  # noqa: F401
import app.models.eleicao  # noqa: F401
import app.models.eleitor  # noqa: F401
import app.models.partido  # noqa: F401
import app.models.registro_votacao  # noqa: F401
import app.models.usuario  # noqa: F401
import app.models.voto  # noqa: F401
