# Dados — GitHub API Data Pipeline

Esta pasta contém os dados e artefatos gerados durante a execução do pipeline de ingestão da API do GitHub.

## Finalidade

A organização dos dados separa os resultados por etapa e responsabilidade, incluindo:

- respostas brutas da API, preservadas por recurso e data de ingestão;
- checkpoints usados para acompanhar o processamento incremental;
- eventos derivados da comparação de snapshots de repositórios.

---

## Estrutura

| Área | Descrição |
| --- | --- |
| [raw](raw/) | Respostas da API e dados estruturados por recurso e data de ingestão |
| [checkpoints](checkpoints/) | Estado de processamento incremental de cada recurso |
| [changes](changes/) | Alterações detectadas entre snapshots de repositórios |

---

## Observações

Os arquivos JSON e Parquet são artefatos gerados pelo pipeline e não são versionados. Os arquivos `.gitkeep` preservam a estrutura das pastas no repositório.
