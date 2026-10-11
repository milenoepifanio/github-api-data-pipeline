
# Arquitetura do GitHub API Data Pipeline

## Sobre

Este documento apresenta a arquitetura técnica do GitHub API Data Pipeline, incluindo seus componentes, responsabilidades, fluxo de dados, organização de diretórios e decisões de implementação.

O projeto utiliza uma arquitetura modular em Python para consumir recursos da API REST do GitHub e armazená-los em uma camada Raw.

O objetivo é manter uma separação clara entre comunicação HTTP, extração de dados, orquestração, persistência e controle operacional.

---

# 1. Visão geral da arquitetura

A arquitetura está organizada em seis componentes principais:

1. Configuração e autenticação.
2. Cliente HTTP e paginação.
3. Módulos de ingestão.
4. Orquestração dos pipelines.
5. Persistência dos dados.
6. Controle operacional e observabilidade.

O fluxo principal é:

```text
                    GitHub REST API
                           |
                           v
                  Autenticação e Token
                           |
                           v
                       Cliente HTTP
                           |
                +----------+----------+
                |          |          |
             Timeout     Retry     Rate Limit
                |          |          |
                +----------+----------+
                           |
                           v
                        Paginação
                           |
                           v
                    Módulos de Ingestão
                           |
          +----------------+----------------+
          |                |                |
       Commits        Repositories       Issues / PRs
          |                |                |
          +----------------+----------------+
                           |
                           v
                   Orquestração
                           |
             +-------------+-------------+
             |             |             |
        Incremental     Checkpoints    Logging
             |             |             |
             +-------------+-------------+
                           |
                           v
                       Raw Storage
                           |
                    +------+------+
                    |             |
                   JSON         Parquet
```

---

# 2. Organização por módulos

## 2.1 Configuração

Diretório:

```text
config/
    config.yaml
```

Centraliza parâmetros de configuração do projeto.

As credenciais são mantidas separadamente das configurações versionadas.

## 2.2 Comunicação com a API

Diretório:

```text
src/api/
    auth.py
    client.py
    pagination.py
```

### auth.py

Responsável pela obtenção e preparação das credenciais utilizadas nas requisições.

### client.py

Implementa o cliente HTTP responsável por:

- Construção e validação de URLs.
- Execução de requisições GET.
- Configuração de timeout.
- Tratamento de respostas HTTP.
- Retry e backoff.
- Tratamento de rate limits.
- Registro de eventos de recuperação.

### pagination.py

Implementa a navegação entre páginas de resultados utilizando as informações de paginação retornadas pela API.

A API do GitHub utiliza o cabeçalho HTTP `Link` para indicar URLs de páginas relacionadas.

---

# 3. Módulos de ingestão

Diretório:

```text
src/ingestion/
    commits.py
    repositories.py
    issues.py
    pull_requests.py
```

Cada módulo representa um recurso da API.

Essa separação facilita:

- Manutenção do código.
- Reutilização do cliente HTTP.
- Evolução individual das regras de ingestão.
- Testes específicos por entidade.
- Inclusão de novos recursos.

Os módulos de ingestão obtêm os registros, enquanto a orquestração controla sua execução e persistência.

---

# 4. Orquestração

Diretório:

```text
src/pipeline/
    main.py
    commits.py
    resources.py
```

## 4.1 main.py

Representa o ponto de entrada principal.

Coordena dois fluxos:

1. Commits Pipeline.
2. Resources Pipeline.

A execução é iniciada com:

```powershell
python -m src.pipeline.main
```

## 4.2 commits.py

Responsável pela ingestão incremental de commits.

Entre suas responsabilidades estão:

- Carregar o checkpoint.
- Definir a referência temporal.
- Consultar os commits.
- Identificar registros incrementais.
- Persistir JSON e Parquet.
- Atualizar o checkpoint após o processamento.
- Registrar logs de execução.

## 4.3 resources.py

Responsável pela execução dos fluxos de:

- Repositories.
- Issues.
- Pull Requests.

A ingestão de repositórios utiliza snapshots e comparação de estados.

Issues e Pull Requests utilizam processamento incremental.

O módulo também registra os resultados operacionais e os eventos de alteração dos repositórios.

---

# 5. Camada Raw

Diretório:

```text
src/storage/
    raw.py
```

A classe `RawStorage` centraliza a persistência dos dados.

## 5.1 JSON

O método `save()` armazena os registros completos recebidos da API.

Essa abordagem preserva informações que não foram selecionadas para o formato estruturado.

## 5.2 Parquet

Os métodos especializados selecionam campos relevantes para cada entidade:

- `save_commits_parquet()`
- `save_repositories_parquet()`
- `save_issues_parquet()`
- `save_pull_requests_parquet()`

O método interno `_save_parquet()` centraliza a criação do DataFrame e a gravação.

Os campos temporais reconhecidos são convertidos para tipos de data com referência UTC, quando aplicável.

## 5.3 Organização física

```text
data/
    raw/
        commits/
            ingestion_date=YYYY-MM-DD/
        repositories/
            ingestion_date=YYYY-MM-DD/
        issues/
            ingestion_date=YYYY-MM-DD/
        pull_requests/
            ingestion_date=YYYY-MM-DD/
```

Os arquivos utilizam timestamps nos nomes para diferenciar lotes de ingestão.

JSON e Parquet são gerados em operações separadas e podem possuir timestamps diferentes.

---

# 6. Controle incremental

Diretório:

```text
src/utils/
    checkpoint.py
```

A classe `CheckpointManager` implementa operações de leitura e escrita.

### load()

Carrega a referência armazenada para uma entidade.

Quando não existe checkpoint, retorna `None`.

### save()

Persiste a referência do último processamento bem-sucedido.

Exemplo de estrutura:

```json
{
  "entity": "commits",
  "last_processed_at": "2026-10-11T13:44:59Z"
}
```

Os checkpoints ficam em:

```text
data/checkpoints/
```

A implementação básica utiliza arquivos JSON locais.

---

# 7. Detecção de alterações em repositórios

A ingestão de repositórios possui uma estratégia específica.

A cada execução:

1. Recupera os repositórios disponíveis.
2. Persiste um snapshot completo.
3. Carrega o estado anterior.
4. Compara os estados.
5. Identifica eventos de alteração.
6. Persiste os eventos detectados.
7. Atualiza o checkpoint de estado.

Os eventos possíveis são:

| Evento | Significado |
|---|---|
| CREATED | Novo repositório identificado |
| UPDATED | Alteração nos metadados monitorados |
| MISSING | Repositório anteriormente conhecido não retornado |
| RESTORED | Repositório anteriormente ausente retornou |

Os eventos são armazenados em:

```text
data/changes/repositories/batches/
```

A estratégia utiliza identificadores determinísticos de lote para evitar a duplicação de eventos quando uma operação é repetida.

Um repositório marcado como ausente permanece no estado armazenado, permitindo identificar um possível retorno.

O evento MISSING representa ausência na consulta realizada, não necessariamente exclusão definitiva do repositório.

---

# 8. Observabilidade

Diretório:

```text
src/utils/
    logger.py
```

O projeto utiliza o módulo `logging` do Python.

Os registros incluem:

- Timestamp.
- Nível de severidade.
- Módulo de origem.
- Mensagem operacional.

Exemplo:

```text
2026-10-11 13:16:34 | INFO | src.pipeline.resources | Repositories retrieved from API | Count=47
```

Os logs são enviados ao terminal e ao arquivo:

```text
logs/github_api.log
```

O arquivo utiliza rotação com limite de tamanho e retenção de arquivos anteriores.

---

# 9. Tratamento de falhas

O cliente HTTP implementa recuperação para erros transitórios.

Os pipelines registram exceções e informações sobre falhas de execução.

Nos cenários testados de persistência de repositórios, falhas simuladas na gravação de snapshots, eventos ou checkpoints impediram o avanço indevido do estado.

Esse comportamento é importante para preservar a capacidade de recuperação.

A implementação não deve ser interpretada como uma transação atômica entre todos os arquivos envolvidos.

---

# 10. Decisões arquiteturais

## 10.1 Arquitetura modular

A separação dos componentes reduz o acoplamento e facilita manutenção e testes.

## 10.2 Persistência dupla

JSON preserva os dados completos, enquanto Parquet disponibiliza uma representação estruturada.

## 10.3 Checkpoints locais

A utilização de JSON simplifica o controle incremental sem depender de banco de dados externo.

## 10.4 Snapshots de repositórios

Como repositórios podem sofrer alterações em seus metadados, a comparação de estados permite detectar eventos relevantes.

## 10.5 Logs estruturados por mensagem

Os registros padronizados facilitam a investigação de falhas e o acompanhamento das execuções.

---

# 11. Limitações e evolução

A arquitetura atual não inclui:

- Camada Silver.
- Orquestração externa.
- Armazenamento em nuvem.
- Deduplicação histórica global.
- Controle transacional distribuído.
- Monitoramento centralizado.

Possíveis evoluções incluem:

- Data Lake em nuvem.
- Transformações com PySpark.
- Persistência atômica de checkpoints.
- Testes automatizados em CI/CD.
- Métricas operacionais.
- Alertas e monitoramento.

---

# 12. Documentos relacionados

- [README](../README.md)
- [Exploração da API](api_exploration.md)
- [Cliente HTTP](client.md)
- [Estratégia Incremental](incremental_strategy.md)
