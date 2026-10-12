# Pipeline — GitHub API Data Pipeline

Esta pasta reúne os pontos de orquestração que conectam a ingestão, o controle incremental e a persistência dos dados.

## Finalidade

Os módulos desta área coordenam a execução dos fluxos de recursos e apoiam:

- processamento de commits;
- execução dos recursos do pipeline;
- inicialização do fluxo principal.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [__init__.py](__init__.py) | Inicialização do pacote |
| [commits.py](commits.py) | Orquestração do fluxo de commits |
| [resources.py](resources.py) | Orquestração dos fluxos de recursos |
| [main.py](main.py) | Ponto de entrada da execução do pipeline |

---

## Observações

Os fluxos utilizam os módulos de [ingestão](../ingestion/) e de [armazenamento](../storage/), além dos utilitários compartilhados.
