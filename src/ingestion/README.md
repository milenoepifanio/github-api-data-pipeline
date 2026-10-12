# Ingestão — GitHub API Data Pipeline

Esta pasta contém os módulos que consultam e preparam os recursos obtidos pela API REST do GitHub.

## Finalidade

Cada módulo concentra a ingestão de um tipo de recurso, apoiando os fluxos de:

- metadados de repositórios;
- commits de um repositório;
- issues;
- pull requests.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [repositories.py](repositories.py) | Ingestão dos metadados de repositórios |
| [commits.py](commits.py) | Ingestão do histórico de commits |
| [issues.py](issues.py) | Ingestão de issues |
| [pull_requests.py](pull_requests.py) | Ingestão de pull requests |

---

## Observações

Os módulos de ingestão utilizam a camada de [API](../api/) e são coordenados pelos fluxos em [pipeline](../pipeline/).
