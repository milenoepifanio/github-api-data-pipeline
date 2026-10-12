# PDI — Evidências de Desenvolvimento Técnico

## Hard Skills — API: Integração com Web APIs

**Projeto:** GitHub API Data Pipeline  
**Competência:** Integração com Web APIs  
**Área:** Engenharia de Dados  
**Linguagem principal:** Python  
**API utilizada:** GitHub REST API  
**Status:** Implementação concluída — validação final e consolidação das evidências

**Repositório:** [github-api-data-pipeline](https://github.com/milenoepifanio/github-api-data-pipeline)

---

# 1. Contexto e objetivo

Esta iniciativa faz parte do Plano de Desenvolvimento Individual (PDI), na competência **Hard Skills — API: Integração com Web APIs**.

O objetivo definido foi:

> Desenvolver um pipeline de dados utilizando uma API pública, aplicando conceitos de integração com Web APIs, resiliência, processamento e persistência de dados para fortalecer competências em Engenharia de Dados.

Para atender a esse objetivo, foi desenvolvido o **GitHub API Data Pipeline**, uma solução em Python que realiza a ingestão de dados da API REST do GitHub, incorporando mecanismos de autenticação, paginação, tratamento de falhas, persistência, incrementalidade e observabilidade.

A escolha do GitHub permitiu trabalhar com uma API pública que oferece autenticação, diferentes recursos, paginação, limites de requisições e dados estruturados em JSON.

O projeto foi organizado em módulos independentes, permitindo separar a comunicação com a API, as regras de ingestão, a persistência e o controle das execuções.

---

# 2. Planejamento original do PDI

## 2.1 Ações previstas

As ações definidas para o desenvolvimento da competência foram:

1. Consumir e integrar dados de uma API pública utilizando Python.
2. Trabalhar com autenticação, parâmetros, paginação e respostas HTTP.
3. Aplicar tratamento de erros, timeout, retry e rate limits.
4. Processar e estruturar dados JSON.
5. Implementar persistência, incrementalidade e logs.
6. Aplicar testes e documentar a solução.

## 2.2 Etapas previstas

| Etapa | Atividade planejada |
|---|---|
| Tarefa 1 | Fundamentos de Web APIs, HTTP e exploração da API selecionada |
| Tarefa 2 | Desenvolvimento da ingestão com Python, incluindo autenticação, parâmetros e paginação |
| Tarefa 3 | Implementação de resiliência: códigos HTTP, timeout, erros, retry/backoff e rate limit |
| Tarefa 4 | Persistência Raw, tratamento dos dados e implementação de carga incremental |
| Tarefa 5 | Testes, logs, consolidação do pipeline e documentação técnica |

---

# 3. Resumo das entregas

O desenvolvimento resultou em um pipeline funcional, organizado em módulos Python e versionado em Git.

A solução implementa:

- Integração autenticada com a API REST do GitHub.
- Requisições HTTP parametrizadas.
- Paginação automática por meio do cabeçalho `Link`.
- Ingestão de commits, repositories, issues e pull requests.
- Tratamento de falhas de conexão e timeout.
- Retry com backoff exponencial.
- Tratamento de limites primários e secundários de requisições.
- Persistência dos dados completos em JSON.
- Estruturação e persistência de dados em Parquet.
- Particionamento por data de ingestão.
- Controle incremental com checkpoints.
- Comparação de snapshots de repositórios.
- Detecção de eventos de criação, atualização, ausência e retorno de repositórios.
- Logging operacional com rotação de arquivos.
- Testes funcionais e de recuperação.
- Documentação da arquitetura e dos componentes.

Essas implementações atendem às cinco etapas técnicas previstas no planejamento do PDI.

---

# 4. Planejado versus realizado

## 4.1 Tarefa 1 — Fundamentos de Web APIs, HTTP e exploração da API

**Objetivo:** compreender os fundamentos de Web APIs e explorar uma API pública, identificando seus recursos, métodos de autenticação, parâmetros, respostas e limitações.

### Atividades realizadas

- Estudo dos conceitos de API REST e comunicação HTTP.
- Exploração da API REST do GitHub.
- Identificação da URL base e dos principais endpoints.
- Análise dos métodos de autenticação.
- Estudo dos códigos de resposta HTTP.
- Exploração de parâmetros de consulta.
- Identificação do mecanismo de paginação.
- Análise dos cabeçalhos de rate limit.
- Avaliação das estruturas JSON retornadas.

### Evidências

| Evidência | Descrição |
|---|---|
| [Exploração da API](api_exploration.md) | Documentação dos conceitos, endpoints, parâmetros, paginação e rate limits |
| [Teste de exploração](../notebooks/test_api.py) | Validação prática de autenticação e consultas à API |


### Resultado

Foi possível compreender o funcionamento da API selecionada e identificar os recursos necessários para a construção do pipeline.

**Status:** Concluída.

---

## 4.2 Tarefa 2 — Desenvolvimento da ingestão com Python

**Objetivo:** desenvolver a integração com a API utilizando Python, incluindo autenticação, parâmetros e paginação.

### Atividades realizadas

- Implementação da autenticação por token.
- Criação de um cliente HTTP reutilizável.
- Configuração de cabeçalhos e parâmetros.
- Desenvolvimento do mecanismo de paginação.
- Implementação de módulos específicos de ingestão.
- Integração de quatro recursos da API.

### Recursos implementados

| Recurso | Finalidade |
|---|---|
| Repositories | Consultar metadados dos repositórios |
| Commits | Recuperar o histórico de commits |
| Issues | Consultar issues do repositório |
| Pull Requests | Recuperar informações de pull requests |

### Evidências

| Evidência | Descrição |
|---|---|
| [Autenticação](../src/api/auth.py) | Gerenciamento das credenciais |
| [Cliente HTTP](../src/api/client.py) | Execução de requisições HTTP |
| [Paginação](../src/api/pagination.py) | Navegação entre páginas de resultados |
| [Ingestão de commits](../src/ingestion/commits.py) | Extração de commits |
| [Ingestão de repositórios](../src/ingestion/repositories.py) | Extração de repositórios |
| [Ingestão de issues](../src/ingestion/issues.py) | Extração de issues |
| [Ingestão de pull requests](../src/ingestion/pull_requests.py) | Extração de pull requests |
| [Exploração da API](api_exploration.md) | Referência técnica da integração |

### Resultado

Foi desenvolvido um conjunto de componentes reutilizáveis para consumir diferentes endpoints da API REST do GitHub.

**Status:** Concluída.

---

## 4.3 Tarefa 3 — Implementação de resiliência

**Objetivo:** implementar mecanismos para tratar falhas de comunicação e respostas HTTP, aumentando a confiabilidade da integração.

### Atividades realizadas

- Configuração de timeout nas requisições.
- Tratamento de erros de conexão.
- Diferenciação de erros recuperáveis e não recuperáveis.
- Implementação de retry.
- Implementação de backoff exponencial.
- Tratamento de respostas HTTP 500, 502, 503 e 504.
- Tratamento de HTTP 429.
- Identificação de cenários de rate limit em respostas HTTP 403.
- Utilização dos cabeçalhos `Retry-After` e `X-RateLimit-Reset`.
- Definição de limites máximos de espera.
- Implementação de exceções específicas.
- Validação de URLs utilizadas na paginação.
- Registro de tentativas e falhas nos logs.

### Evidências

| Evidência | Descrição |
|---|---|
| [Cliente HTTP](../src/api/client.py) | Implementação de timeout, retry, backoff e rate limits |
| [Exceções](../src/utils/exceptions.py) | Definição das exceções personalizadas |
| [Teste de recuperação](../notebooks/test_client_recovery.py) | Validação de cenários simulados de falha |
| [Documentação do cliente](client.md) | Explicação dos mecanismos de resiliência |

### Testes realizados

Foram validados oito cenários:

1. HTTP 401 sem retry.
2. HTTP 403 sem rate limit.
3. HTTP 503 com recuperação.
4. Timeout com tentativas esgotadas.
5. Rate limit secundário com recuperação.
6. Espera superior ao limite permitido.
7. Bloqueio de URL de paginação insegura.
8. Rejeição de configuração inválida.

Todos os cenários foram aprovados nos testes realizados.

### Resultado

O cliente passou a possuir mecanismos para lidar com falhas transitórias e limites de requisições, além de fornecer exceções específicas para facilitar a identificação dos problemas.

**Status:** Concluída.

---

## 4.4 Tarefa 4 — Persistência Raw, tratamento e carga incremental

**Objetivo:** estruturar os dados recebidos da API, implementar sua persistência e desenvolver mecanismos de processamento incremental.

### Atividades realizadas

- Implementação da camada Raw.
- Persistência das respostas completas em JSON.
- Seleção e estruturação de campos relevantes.
- Conversão de campos temporais.
- Persistência dos dados estruturados em Parquet.
- Organização dos arquivos por data de ingestão.
- Implementação do gerenciamento de checkpoints.
- Desenvolvimento de estratégias incrementais para commits, issues e pull requests.
- Implementação de snapshots completos de repositórios.
- Comparação entre estados de repositórios.
- Detecção de eventos `CREATED`, `UPDATED`, `MISSING` e `RESTORED`.
- Implementação de controle de idempotência para lotes de eventos de repositórios.

### Evidências

| Evidência | Descrição |
|---|---|
| [Raw Storage](../src/storage/raw.py) | Persistência em JSON e Parquet |
| [Checkpoint Manager](../src/utils/checkpoint.py) | Gerenciamento de checkpoints |
| [Pipeline de commits](../src/pipeline/commits.py) | Processamento incremental de commits |
| [Pipeline de recursos](../src/pipeline/resources.py) | Ingestão dos demais recursos e comparação de estados |
| [Estratégia incremental](incremental_strategy.md) | Documentação das regras de incrementalidade |
| [Teste de Parquet](../notebooks/test_parquet.py) | Validação dos arquivos estruturados |
| [Teste de checkpoint](../notebooks/test_checkpoint.py) | Validação isolada dos checkpoints |
| [Teste incremental](../notebooks/test_incremental.py) | Validação do processamento incremental |
| [Teste de alterações](../notebooks/test_repository_changes.py) | Validação dos eventos e da idempotência |

### Organização dos dados

Os arquivos são armazenados na estrutura:

```text
data/raw/
    commits/
    repositories/
    issues/
    pull_requests/
```

Cada entidade possui partições por data de ingestão:

```text
ingestion_date=YYYY-MM-DD/
```

Os checkpoints são armazenados em:

```text
data/checkpoints/
```

Os eventos de alteração dos repositórios são armazenados em:

```text
data/changes/repositories/batches/
```

### Resultado

Foi implementada uma camada de persistência que mantém os dados completos recebidos da API e uma representação estruturada em Parquet.

Também foram implementados mecanismos para reduzir reprocessamentos e identificar alterações nos recursos monitorados.

**Status:** Concluída.

---

## 4.5 Tarefa 5 — Testes, logs, consolidação e documentação

**Objetivo:** validar o funcionamento do pipeline, implementar observabilidade e consolidar a documentação técnica.

### Atividades realizadas

- Implementação de logging com níveis de severidade.
- Registro de início e término das execuções.
- Registro de quantidade de registros processados.
- Registro de tempo de execução.
- Registro de falhas e exceções.
- Implementação de rotação dos arquivos de log.
- Desenvolvimento de testes funcionais.
- Desenvolvimento de testes de recuperação de falhas.
- Validação de checkpoints e incrementalidade.
- Validação de integridade dos arquivos Raw.
- Execução integrada do pipeline.
- Documentação da arquitetura.
- Documentação da API.
- Documentação do cliente HTTP.
- Documentação da estratégia incremental.
- Consolidação do README.

### Evidências

| Evidência | Descrição |
|---|---|
| [Logger](../src/utils/logger.py) | Configuração do logging |
| [Pipeline principal](../src/pipeline/main.py) | Orquestração da execução |
| [Teste de integridade](../notebooks/test_raw_integrity.py) | Verificação de JSON, Parquet e identificadores |
| [Teste de recuperação](../notebooks/test_client_recovery.py) | Simulação de falhas HTTP |
| [Teste de alterações](../notebooks/test_repository_changes.py) | Validação de eventos e reexecução |
| [README](../README.md) | Apresentação, instalação, execução e testes |
| [Arquitetura](architecture.md) | Descrição dos componentes e do fluxo |
| [Exploração da API](api_exploration.md) | Documentação dos endpoints |
| [Cliente HTTP](client.md) | Documentação da resiliência |
| [Estratégia incremental](incremental_strategy.md) | Documentação da incrementalidade |

### Resultado da validação de integridade

Em 11/10/2026, foi executado:

```powershell
python -m notebooks.test_raw_integrity
```

Resultado:

| Entidade | Registros | Colunas | Status |
|---|---:|---:|---|
| Commits | 14 | 7 | PASS |
| Repositories | 47 | 18 | PASS |
| Issues | 2 | 14 | PASS |
| Pull Requests | 14 | 15 | PASS |

**Total:** 77 registros nos arquivos selecionados para validação.

Foram verificadas:

- Leitura dos arquivos JSON.
- Leitura dos arquivos Parquet.
- Presença das colunas obrigatórias.
- Unicidade dos identificadores dentro dos arquivos selecionados.
- Consistência de identificadores entre JSON e Parquet.
- Preenchimento dos timestamps de ingestão.

Os resultados demonstram a integridade dos arquivos selecionados para o teste, sem representar uma auditoria completa de todos os lotes históricos.

### Resultado da execução integrada

O pipeline também foi executado por meio do comando:

```powershell
python -m src.pipeline.main
```

A execução integrada foi concluída com status `SUCCESS`, confirmando a operação dos fluxos de ingestão e a integração entre seus componentes.

**Status:** Implementação e testes concluídos. Documentação produzida, sujeita à revisão final e ao versionamento.

---

# 5. Matriz de rastreabilidade do PDI

A matriz abaixo relaciona as ações previstas às principais evidências técnicas.

| Ação prevista | Implementação | Evidência | Status |
|---|---|---|---|
| Consumir API pública com Python | Integração com GitHub REST API | [Módulos de ingestão](../src/ingestion/) | Concluído |
| Trabalhar com autenticação | Token de acesso | [auth.py](../src/api/auth.py) | Concluído |
| Utilizar parâmetros HTTP | Requisições parametrizadas | [client.py](../src/api/client.py) | Concluído |
| Implementar paginação | Paginação pelo cabeçalho Link | [pagination.py](../src/api/pagination.py) | Concluído |
| Tratar respostas HTTP | Validação de status e exceções | [client.py](../src/api/client.py) | Concluído |
| Aplicar timeout | Timeout configurável | [client.py](../src/api/client.py) | Concluído |
| Implementar retry e backoff | Recuperação de falhas transitórias | [client.py](../src/api/client.py) | Concluído |
| Tratar rate limits | Controle de espera e limites | [client.md](client.md) | Concluído |
| Processar JSON | Extração e estruturação de campos | [raw.py](../src/storage/raw.py) | Concluído |
| Persistir dados | JSON e Parquet | [raw.py](../src/storage/raw.py) | Concluído |
| Implementar incrementalidade | Checkpoints e regras incrementais | [incremental_strategy.md](incremental_strategy.md) | Concluído |
| Implementar logs | Logging operacional | [logger.py](../src/utils/logger.py) | Concluído |
| Aplicar testes | Scripts de validação funcional | [Testes](../notebooks/) | Concluído |
| Documentar a solução | Documentação técnica | [Documentação](./) | Produzido |

---

# 6. Resultados esperados versus resultados alcançados

## 6.1 Integrações robustas com Web APIs

**Esperado:** desenvolver a capacidade de construir integrações robustas com APIs.

**Alcançado:** implementação de um cliente HTTP reutilizável, com autenticação, paginação, tratamento de falhas e recuperação automática em cenários transitórios.

## 6.2 Autenticação, paginação e respostas HTTP

**Esperado:** adquirir domínio prático desses conceitos.

**Alcançado:** aplicação de autenticação por token, parâmetros de requisição, paginação pelo cabeçalho Link e tratamento de códigos HTTP.

## 6.3 Resiliência, incrementalidade e observabilidade

**Esperado:** aplicar mecanismos para melhorar a confiabilidade e o controle das execuções.

**Alcançado:** implementação de retry, backoff, rate limits, checkpoints, detecção de alterações, logs e testes de recuperação.

## 6.4 Autonomia na construção de pipelines

**Esperado:** ampliar a autonomia no desenvolvimento de integrações para Engenharia de Dados.

**Alcançado:** desenvolvimento de uma solução modular, com múltiplos recursos, persistência estruturada, execução integrada e documentação técnica.

A implementação evidencia a aplicação prática dos conceitos estudados. A evolução da autonomia profissional é um resultado qualitativo a ser avaliado no contexto do PDI.

---

# 7. Entregáveis

| Entregável previsto | Evidência | Situação |
|---|---|---|
| Pipeline funcional e versionado | [Código-fonte](../src/) | Implementado; confirmar publicação da versão final |
| Dados Raw e estruturados | [Raw Storage](../src/storage/raw.py) | Implementado e validado localmente |
| Testes de execução | [Scripts de teste](../notebooks/) | Implementados e executados |
| Logs de execução | [Logger](../src/utils/logger.py) | Implementado e validado |
| Documentação técnica | [Documentação](./) | Produzida; confirmar versionamento |
| Arquitetura da solução | [architecture.md](architecture.md) | Documentada |

Os diretórios de dados e logs podem não estar versionados no GitHub, conforme as regras do `.gitignore`.

Por isso, a comprovação dessas entregas pode incluir capturas de tela ou registros de execução anexados ao PDI.

---

# 8. Desafios técnicos e aprendizados

## 8.1 Autenticação

Durante a exploração inicial, foi identificado um erro HTTP 401 relacionado à ausência ou configuração incorreta do token.

A correção permitiu compreender a importância dos cabeçalhos de autenticação e do gerenciamento seguro de credenciais.

## 8.2 Organização dos módulos

Durante o desenvolvimento, foram enfrentados problemas relacionados a importações Python, incluindo importação circular e resolução de pacotes.

A organização modular e a execução por meio de `python -m` contribuíram para resolver esses problemas.

## 8.3 Paginação

A implementação da paginação exigiu compreender o cabeçalho Link e o comportamento de múltiplas requisições.

Esse aprendizado permitiu construir um mecanismo reutilizável para os recursos consultados.

## 8.4 Incrementalidade

A implementação de checkpoints demonstrou a importância de controlar o estado das execuções.

Durante os testes, o retrocesso manual de um checkpoint provocou o reprocessamento de registros já armazenados.

A partir dessa observação, o teste de checkpoints foi isolado em um diretório temporário.

## 8.5 Recuperação de falhas

Os testes simulados demonstraram a necessidade de diferenciar falhas recuperáveis e definitivas.

A implementação passou a considerar limites de tentativas, tempos máximos de espera e exceções específicas.

## 8.6 Idempotência

A comparação de estados dos repositórios permitiu explorar o conceito de idempotência.

O controle de lotes determinísticos contribuiu para evitar duplicações dos eventos durante reexecuções.

---

# 9. Limitações conhecidas

Apesar de atender ao escopo do PDI, o projeto possui oportunidades de evolução.

As principais limitações são:

- Armazenamento local dos dados.
- Ausência de uma camada Silver.
- Ausência de deduplicação histórica global entre lotes Raw.
- Ausência de orquestração externa.
- Ausência de execução automatizada por CI/CD.
- Checkpoints básicos sem persistência atômica.
- Ausência de monitoramento centralizado.

Essas limitações não impedem a utilização do projeto como demonstração dos conceitos previstos no PDI.

Elas representam possibilidades de aprofundamento técnico.

---

# 10. Próximos passos

As melhorias abaixo são propostas de evolução e não fazem parte das entregas concluídas.

## 10.1 Ampliação dos recursos da API

### Commits e merges

Explorar informações adicionais sobre:

- Histórico de merges.
- Commits associados a pull requests.
- Identificação de commits de merge.
- Datas de integração das alterações.
- Branches de origem e destino.

**Objetivo:** enriquecer a análise do ciclo de desenvolvimento dos repositórios.

### Participantes e contribuidores

Integrar informações relacionadas a:

- Contributors.
- Authors.
- Committers.
- Participantes de issues.
- Participantes de pull requests.

**Objetivo:** permitir análises de colaboração e participação nos projetos.

### Detalhamento de pull requests

Explorar recursos como:

- Reviews.
- Review comments.
- Commits de pull requests.
- Arquivos alterados.
- Informações de merge.

**Objetivo:** ampliar a granularidade dos dados de desenvolvimento.

### Descrições e metadados

Avaliar a incorporação de:

- Descrições de repositórios.
- Topics.
- Linguagens utilizadas.
- Metadados adicionais de issues.
- Labels.
- Milestones.

**Objetivo:** enriquecer o contexto analítico dos recursos coletados.

---

## 10.2 Evolução da arquitetura

### Camada Silver

Implementar uma camada de transformação para:

- Padronização de schemas.
- Tratamento de valores nulos.
- Deduplicação.
- Normalização de entidades.
- Relacionamento entre recursos.

### Armazenamento em nuvem

Avaliar a migração dos dados para um serviço de armazenamento de objetos.

### Orquestração

Implementar agendamento e acompanhamento automatizado das execuções.

### Qualidade de dados

Ampliar as validações para incluir:

- Integridade referencial.
- Validação de schemas.
- Controle de duplicidades históricas.
- Verificação de campos obrigatórios.
- Monitoramento de volumes.

### Observabilidade

Evoluir os logs para incluir:

- Métricas consolidadas.
- Histórico de execuções.
- Alertas de falhas.
- Indicadores de desempenho.

---

# 11. Conclusão

O desenvolvimento do GitHub API Data Pipeline permitiu aplicar os conceitos previstos no PDI de Integração com Web APIs em uma solução funcional de Engenharia de Dados.

O projeto contempla o consumo de uma API pública, autenticação, paginação, tratamento de respostas HTTP, resiliência, estruturação de JSON, persistência em JSON e Parquet, incrementalidade, checkpoints, logging e testes.

A implementação também possibilitou explorar conceitos complementares, como comparação de snapshots, detecção de alterações e idempotência.

Os resultados demonstram a aplicação prática das competências previstas e estabelecem uma base para evoluções futuras em processamento, qualidade, governança e arquitetura de dados.

A consolidação dos commits, da documentação versionada e das evidências visuais permitirá finalizar a comprovação formal das entregas no PDI.

---

# 13. Referências

## Documentação do projeto

- [README](../README.md)
- [Arquitetura](architecture.md)
- [Exploração da API](api_exploration.md)
- [Cliente HTTP](client.md)
- [Estratégia Incremental](incremental_strategy.md)

## Documentação externa

- [GitHub REST API](https://docs.github.com/en/rest)
- [Autenticação](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
- [Paginação](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
- [Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
