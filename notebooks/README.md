# Notebooks e Validações — GitHub API Data Pipeline

Esta pasta reúne scripts de exploração e validação usados durante o desenvolvimento e a verificação do pipeline de dados da API do GitHub.

## Finalidade

Os arquivos apoiam a análise e os testes de partes específicas da solução, incluindo:

- comunicação com a API e recuperação de falhas;
- ingestão de recursos e processamento incremental;
- persistência e integridade dos dados;
- checkpoints e detecção de alterações em repositórios.

---

## Estrutura

| Arquivo | Descrição |
| --- | --- |
| [test_api.py](test_api.py) | Verificações relacionadas ao acesso à API |
| [test_client_recovery.py](test_client_recovery.py) | Validação da recuperação do cliente HTTP |
| [test_checkpoint.py](test_checkpoint.py) | Verificação do controle por checkpoints |
| [test_incremental.py](test_incremental.py) | Exploração da estratégia de ingestão incremental |
| [test_parquet.py](test_parquet.py) | Verificação da persistência em Parquet |
| [test_raw_integrity.py](test_raw_integrity.py) | Validação da integridade dos dados da camada Raw |
| [test_repository_changes.py](test_repository_changes.py) | Verificação da detecção de alterações em repositórios |
| [test_resources.py](test_resources.py) | Verificação da ingestão dos recursos da API |
| [test_resources_pipeline.py](test_resources_pipeline.py) | Validação da execução do pipeline de recursos |

---

## Observações

Apesar do nome da pasta, o conteúdo atual consiste em scripts Python; não há arquivos de notebook Jupyter nesta pasta.
