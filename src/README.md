# Código-fonte — GitHub API Data Pipeline

Esta pasta organiza os módulos Python que implementam a integração com a API do GitHub, a ingestão, a orquestração e o armazenamento dos dados.

## Finalidade

O código está separado por responsabilidade para apoiar:

- comunicação autenticada e paginada com a API;
- ingestão de diferentes recursos do GitHub;
- execução e coordenação dos fluxos do pipeline;
- persistência e controles operacionais reutilizáveis.

---

## Estrutura

| Área | Descrição |
| --- | --- |
| [api](api/) | Autenticação, cliente HTTP e paginação |
| [ingestion](ingestion/) | Leitura dos recursos disponibilizados pela API |
| [pipeline](pipeline/) | Orquestração e execução dos fluxos de dados |
| [storage](storage/) | Persistência dos dados ingeridos |
| [utils](utils/) | Checkpoints, exceções e logging |

---

## Observações

Os módulos desta pasta implementam a camada de aplicação descrita na documentação do projeto; os dados gerados são mantidos em [data](../data/).
