# Alterações de Repositórios — GitHub API Data Pipeline

Esta pasta armazena os eventos identificados ao comparar snapshots de repositórios entre execuções do pipeline.

## Finalidade

Os arquivos desta área registram mudanças detectadas nos metadados dos repositórios, incluindo:

- criação ou atualização de repositórios;
- repositórios que deixaram de aparecer na consulta;
- repositórios anteriormente ausentes que voltaram a aparecer;
- resultados organizados por data de ingestão e lotes.

---

## Estrutura

| Área | Descrição |
| --- | --- |
| [batches](batches/) | Arquivos de alterações agrupados em lotes |
| [ingestion_date=2026-10-11](ingestion_date=2026-10-11/) | Alterações associadas à data de ingestão de 11/10/2026 |

---

## Observações

Esta área guarda resultados incrementais derivados da comparação de repositórios. Os snapshots e checkpoints correspondentes são mantidos separadamente em [data](../..).
