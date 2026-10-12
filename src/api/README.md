# API — GitHub API Data Pipeline

Esta pasta contém os componentes responsáveis pela comunicação com a API REST do GitHub.

## Finalidade

Os módulos oferecem suporte para:

- carregar e aplicar as credenciais de acesso;
- realizar requisições HTTP e tratar condições de recuperação;
- percorrer resultados paginados da API.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [auth.py](auth.py) | Autenticação e configuração de acesso |
| [client.py](client.py) | Cliente HTTP para as chamadas à API |
| [pagination.py](pagination.py) | Tratamento da paginação dos resultados |

---

## Observações

Esta camada é utilizada pelos módulos de [ingestão](../ingestion/) para consultar os recursos do GitHub.
