# Checkpoints — GitHub API Data Pipeline

Esta pasta armazena os pontos de controle usados pelo pipeline para acompanhar o estado das ingestões.

## Finalidade

Os checkpoints permitem retomar ou avançar o processamento incremental sem consultar novamente todo o histórico, mantendo o estado de cada recurso:

- referência temporal ou identificador de progresso;
- estado da última execução processada;
- controle independente por tipo de recurso.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [commits.json](commits.json) | Estado incremental da ingestão de commits |
| [issues_milenoepifanio_github-api-data-pipeline.json](issues_milenoepifanio_github-api-data-pipeline.json) | Estado da ingestão de issues do repositório |
| [pull_requests_milenoepifanio_github-api-data-pipeline.json](pull_requests_milenoepifanio_github-api-data-pipeline.json) | Estado da ingestão de pull requests do repositório |
| [repositories_milenoepifanio.json](repositories_milenoepifanio.json) | Estado usado para comparar snapshots de repositórios |

---

## Observações

Os arquivos de checkpoint são dados locais gerados durante a execução e não são versionados. O `.gitkeep` mantém a pasta representada no repositório.
