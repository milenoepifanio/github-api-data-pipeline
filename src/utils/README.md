# Utilitários — GitHub API Data Pipeline

Esta pasta reúne funcionalidades de apoio compartilhadas pelos componentes do pipeline.

## Finalidade

Os utilitários centralizam recursos transversais do projeto, como:

- registro do estado de processamento por checkpoints;
- tipos e tratamento de exceções;
- logging operacional.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [checkpoint.py](checkpoint.py) | Leitura e atualização de checkpoints |
| [exceptions.py](exceptions.py) | Exceções específicas da aplicação |
| [logger.py](logger.py) | Configuração e suporte ao logging |

---

## Observações

Esses recursos são utilizados pelas camadas de ingestão, pipeline e armazenamento.
