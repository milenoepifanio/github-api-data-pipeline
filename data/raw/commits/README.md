# Commits — Dados Brutos

Esta pasta organiza os dados de commits obtidos da API do GitHub e armazenados na camada Raw.

## Finalidade

Os dados são particionados por data de ingestão para facilitar a rastreabilidade das execuções. Cada execução pode produzir:

- a resposta recebida da API em JSON;
- uma representação estruturada em Parquet;
- arquivos identificados pelo repositório e horário de ingestão.

---

## Estrutura

| Pasta | Descrição |
| --- | --- |
| [ingestion_date=2026-10-02](ingestion_date=2026-10-02/) | Dados ingeridos em 02/10/2026 |
| [ingestion_date=2026-10-05](ingestion_date=2026-10-05/) | Dados ingeridos em 05/10/2026 |
| [ingestion_date=2026-10-10](ingestion_date=2026-10-10/) | Dados ingeridos em 10/10/2026 |
| [ingestion_date=2026-10-11](ingestion_date=2026-10-11/) | Dados ingeridos em 11/10/2026 |

---

## Observações

Os arquivos de dados são gerados durante a ingestão e ignorados pelo Git. Os marcadores `.gitkeep` mantêm as pastas de partição representadas quando seus dados não estão versionados.
