# Testes — GitHub API Data Pipeline

Esta pasta contém os testes automatizados que verificam os componentes e os fluxos principais do projeto.

## Finalidade

Os testes ajudam a validar:

- autenticação, chamadas HTTP e paginação;
- ingestão e execução dos pipelines;
- armazenamento Raw e controle por checkpoints;
- utilitários e configuração compartilhada dos testes.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [conftest.py](conftest.py) | Fixtures e configurações compartilhadas do pytest |
| [main.py](main.py) | Ponto de entrada auxiliar relacionado aos testes |
| [test_auth_client.py](test_auth_client.py) | Testes de autenticação e cliente HTTP |
| [test_pagination_ingestion.py](test_pagination_ingestion.py) | Testes de paginação e ingestão |
| [test_pipelines.py](test_pipelines.py) | Testes de execução dos pipelines |
| [test_storage_checkpoint.py](test_storage_checkpoint.py) | Testes de armazenamento e checkpoints |
| [test_utils.py](test_utils.py) | Testes dos utilitários do projeto |

---

## Observações

Os testes desta pasta complementam os scripts de validação mantidos em [notebooks](../notebooks/).
