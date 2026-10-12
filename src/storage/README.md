# Armazenamento — GitHub API Data Pipeline

Esta pasta contém os componentes responsáveis por persistir os dados recebidos pelo pipeline.

## Finalidade

A camada de armazenamento preserva os resultados da ingestão para consulta e processamento posterior, incluindo:

- respostas brutas em JSON;
- dados estruturados em formatos utilizados pelo projeto;
- organização dos arquivos por recurso e execução.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [raw.py](raw.py) | Persistência e operações relacionadas à camada Raw |

---

## Observações

Os arquivos gerados são organizados na pasta [data](../../data/); esta área contém a implementação da persistência.
