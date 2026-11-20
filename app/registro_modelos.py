"""Registro dos modelos ORM.

Quando os módulos de domínio existirem, este arquivo importará os modelos de todos eles
(identidade, eleitores, candidatos, eleicoes e votacao). O Alembic importa este arquivo para
enxergar todas as tabelas em `Base.metadata`.
"""
