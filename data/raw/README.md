# Dados Brutos — GitHub API Data Pipeline

Esta pasta contém os dados obtidos da API REST do GitHub e preservados na camada Raw do pipeline.

## Finalidade

A camada Raw mantém os resultados da ingestão organizados por recurso e data, incluindo:

- respostas originais da API em JSON;
- representações estruturadas em Parquet;
- arquivos separados por execução para apoiar rastreabilidade e validação.

---

## Estrutura

| Área | Descrição |
| --- | --- |
| [commits](commits/) | Dados de commits, organizados por data de ingestão |
| [issues](issues/) | Dados de issues, organizados por data de ingestão |
| [pull_requests](pull_requests/) | Dados de pull requests, organizados por data de ingestão |
| [repositories](repositories/) | Snapshots dos repositórios, organizados por data de ingestão |

---

## Observações

Os arquivos JSON e Parquet são artefatos gerados pelo pipeline e não são versionados. Os arquivos README e `.gitkeep` preservam a documentação e a estrutura de diretórios no repositório.
