# GitHub REST API — Exploração da API

## Sobre

Este documento registra a exploração inicial da **GitHub REST API** e as decisões técnicas adotadas para o projeto **GitHub API Data Pipeline**.

O projeto faz parte do desenvolvimento da hard skill **API — Integração com Web APIs**, com foco na construção de uma integração robusta utilizando Python.

O objetivo não é apenas consumir endpoints, mas aplicar conceitos importantes para Engenharia de Dados, como:

- autenticação;
- parâmetros de requisição;
- paginação;
- tratamento de respostas HTTP;
- timeout;
- retry e exponential backoff;
- rate limit;
- processamento de JSON;
- persistência de dados Raw;
- transformação e estruturação dos dados;
- carga incremental;
- logs;
- testes;
- documentação.

---

# 1. API selecionada

A API escolhida para o projeto foi a **GitHub REST API**.

Documentação oficial:

`https://docs.github.com/rest`

A escolha foi realizada porque a API permite trabalhar, em um cenário real, com grande parte dos conceitos previstos no PDI, incluindo autenticação, paginação, rate limit, parâmetros HTTP, respostas JSON e estratégias de incrementalidade.

A API disponibiliza diferentes recursos relacionados entre si, permitindo construir um pipeline com múltiplas entidades e não apenas realizar requisições isoladas.

Além disso, a GitHub REST API disponibiliza informações de rate limit nos headers HTTP e utiliza mecanismos padronizados de paginação por meio do header `Link`, permitindo explorar características importantes do protocolo HTTP durante o desenvolvimento.

---

# 2. Objetivo do pipeline

O pipeline será responsável por coletar dados de repositórios do GitHub por meio da REST API, persistir as respostas originais e posteriormente transformar os dados em estruturas adequadas para consumo analítico.

Fluxo inicial:

```text
GitHub REST API
       │
       ▼
Python API Client
       │
       ├── Authentication
       ├── Parameters
       ├── Pagination
       ├── Timeout
       ├── Retry
       ├── Backoff
       └── Rate Limit
       │
       ▼
Raw / Bronze
Original JSON
       │
       ▼
Processing
       │
       ├── Normalize
       ├── Flatten
       ├── Cast
       ├── Validate
       └── Deduplicate
       │
       ▼
Silver
Structured Data
```

Além do fluxo principal, o pipeline deverá produzir logs e metadados de execução.

---

# 3. REST API

A GitHub REST API utiliza métodos HTTP padrão e retorna, em sua maioria, dados no formato JSON.

Base URL:

```text
https://api.github.com
```

A API possui versionamento baseado em data.

A versão utilizada inicialmente pelo projeto será:

```text
2026-03-10
```

A versão será informada por meio do header:

```http
X-GitHub-Api-Version: 2026-03-10
```

Também será utilizado o header recomendado:

```http
Accept: application/vnd.github+json
```

Exemplo de endpoint:

```http
GET /repos/{owner}/{repo}
```

Exemplo completo:

```text
https://api.github.com/repos/{owner}/{repo}
```

Inicialmente, o projeto será concentrado em operações de leitura utilizando o método HTTP `GET`.

---

# 4. Recursos selecionados

A primeira versão do pipeline trabalhará com quatro entidades principais:

```text
Repository
   │
   ├── Commits
   ├── Pull Requests
   └── Issues
```

## 4.1 Repositories

Representa o repositório que será utilizado como origem para as demais entidades.

Endpoint principal:

```http
GET /repos/{owner}/{repo}
```

Também poderão ser consultados os repositórios acessíveis pelo usuário autenticado:

```http
GET /user/repos
```

Exemplos de informações esperadas:

- identificador do repositório;
- nome;
- nome completo;
- proprietário;
- descrição;
- URL;
- visibilidade;
- branch padrão;
- linguagem principal;
- datas de criação e atualização;
- informações gerais do repositório.

Durante a exploração inicial, o endpoint:

```http
GET /user/repos
```

foi utilizado com sucesso para validar autenticação e query parameters.

Exemplo:

```http
GET /user/repos?per_page=5&sort=updated
```

---

## 4.2 Commits

Representa os commits existentes no repositório.

Endpoint:

```http
GET /repos/{owner}/{repo}/commits
```

A API permite utilizar parâmetros como:

```text
sha
path
author
committer
since
until
per_page
page
```

Os parâmetros `since` e `until` são especialmente relevantes para o estudo da estratégia de carga incremental.

Exemplo:

```http
GET /repos/{owner}/{repo}/commits?since=2026-09-01T00:00:00Z
```

Os valores temporais deverão seguir o formato ISO 8601 esperado pela API.

---

## 4.3 Pull Requests

Representa as Pull Requests associadas ao repositório.

Endpoint:

```http
GET /repos/{owner}/{repo}/pulls
```

Essa entidade permitirá trabalhar com informações relacionadas ao fluxo de desenvolvimento e integração de código.

Entre os parâmetros disponíveis estão:

```text
state
head
base
sort
direction
per_page
page
```

A estratégia incremental será avaliada considerando os filtros e campos temporais disponibilizados pelo recurso.

---

## 4.4 Issues

Representa as Issues associadas ao repositório.

Endpoint:

```http
GET /repos/{owner}/{repo}/issues
```

Essa entidade permitirá trabalhar com informações de acompanhamento de atividades e relacioná-las ao repositório.

Entre os parâmetros que poderão ser explorados estão:

```text
state
labels
sort
direction
since
per_page
page
```

O parâmetro `since` é especialmente relevante porque permite recuperar registros atualizados após determinado instante.

Uma característica importante da GitHub API é que endpoints de Issues podem também retornar Pull Requests.

Registros que representam Pull Requests possuem informações específicas de `pull_request` no JSON.

Essa característica deverá ser considerada durante o processamento para evitar a interpretação incorreta de Pull Requests como Issues comuns.

---

# 5. Autenticação

Embora determinados dados públicos possam ser consultados sem autenticação, o pipeline utilizará autenticação para exercitar esse conceito e trabalhar de forma mais próxima de uma integração real.

A estratégia inicial será utilizar um **Fine-grained Personal Access Token**.

O token será enviado pelo header:

```http
Authorization: Bearer <access_token>
```

Também serão enviados:

```http
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2026-03-10
```

O token não será armazenado diretamente no código-fonte.

As configurações locais serão mantidas em:

```text
.env
```

Exemplo:

```dotenv
GITHUB_BASE_URL=https://api.github.com
GITHUB_TOKEN=
```

O arquivo `.env` será ignorado pelo Git.

O repositório disponibilizará apenas:

```text
.env.example
```

sem nenhuma credencial real.

As permissões concedidas ao token deverão seguir o princípio de menor privilégio.

---

# 6. Validação inicial da autenticação

A autenticação foi validada utilizando o endpoint:

```http
GET /user
```

O endpoint retornou:

```text
Status: 200
```

confirmando que:

```text
.env
   │
   ▼
GITHUB_TOKEN
   │
   ▼
auth.py
   │
   ▼
Authorization: Bearer
   │
   ▼
client.py
   │
   ▼
GitHub REST API
   │
   ▼
200 OK
```

Com isso, foi validado o fluxo inicial de autenticação entre a aplicação Python e a GitHub REST API.

---

# 7. Parâmetros

Os endpoints da API permitem utilizar query parameters para controlar filtros, paginação, ordenação e comportamento das requisições.

Exemplo:

```http
GET /user/repos?per_page=5&sort=updated
```

Os parâmetros serão enviados pelo cliente HTTP de forma estruturada.

Exemplo conceitual em Python:

```python
params = {
    "per_page": 5,
    "sort": "updated"
}
```

A biblioteca HTTP será responsável por transformar os parâmetros na query string correspondente.

Durante a exploração inicial foi validada a geração da URL:

```text
https://api.github.com/user/repos?per_page=5&sort=updated
```

A intenção é evitar a montagem manual das URLs sempre que possível.

---

# 8. Paginação

A GitHub REST API utiliza paginação quando um endpoint possui uma quantidade de registros maior que aquela retornada em uma única resposta.

Muitos endpoints retornam inicialmente até 30 registros por página.

Quando suportado pelo endpoint, o parâmetro:

```text
per_page
```

permite controlar a quantidade de registros retornados.

Para a maioria dos endpoints paginados, o valor máximo é:

```text
100
```

Exemplo:

```http
GET /repos/{owner}/{repo}/issues?per_page=100
```

## 8.1 Header Link

A estratégia principal de paginação do pipeline será baseada no header HTTP:

```text
Link
```

Quando existem páginas adicionais, o GitHub pode retornar referências como:

```text
rel="prev"
rel="next"
rel="first"
rel="last"
```

Exemplo conceitual:

```text
<https://api.github.com/...?...page=2>; rel="next"
<https://api.github.com/...?...page=10>; rel="last"
```

Nem todas as relações estarão necessariamente disponíveis em todas as respostas.

A implementação não deverá depender da construção manual de:

```text
page + 1
```

A estratégia preferencial será utilizar a URL associada a:

```text
rel="next"
```

retornada pela própria API.

Fluxo:

```text
Page 1
   │
   │ Link: rel="next"
   ▼
Page 2
   │
   │ Link: rel="next"
   ▼
Page 3
   │
   ▼
...
```

A biblioteca `requests` interpreta o header `Link` e disponibiliza essas informações por meio de:

```python
response.links
```

permitindo obter a próxima URL por meio de:

```python
response.links.get("next", {}).get("url")
```

## 8.2 Validação da paginação

A implementação foi validada utilizando um endpoint público com volume suficiente para gerar múltiplas páginas.

Foi configurado:

```text
per_page=5
```

e obtido:

```text
Page 1: 5 records
Page 2: 5 records
Page 3: 5 records
```

Com isso, foi validado o fluxo:

```text
GitHubPaginator
       │
       ▼
Request Page 1
       │
       ▼
Read Link Header
       │
       ▼
rel="next"
       │
       ▼
Request Next URL
       │
       ▼
Next Page
```

---

# 9. Respostas HTTP

O cliente deverá interpretar os códigos HTTP retornados pela API.

Alguns códigos relevantes para o projeto são:

| Código | Significado | Tratamento esperado |
|---|---|---|
| `200` | Requisição realizada com sucesso | Processar resposta |
| `201` | Recurso criado | Registrar sucesso quando aplicável |
| `204` | Sucesso sem conteúdo | Finalizar processamento sem tentar interpretar JSON |
| `304` | Conteúdo não modificado | Avaliar uso em requisições condicionais |
| `400` | Requisição inválida | Registrar erro e revisar parâmetros |
| `401` | Não autenticado | Interromper e registrar erro de autenticação |
| `403` | Acesso proibido ou possível rate limit | Analisar headers e contexto da resposta |
| `404` | Recurso não encontrado | Registrar recurso/endpoint não encontrado |
| `409` | Conflito | Avaliar contexto específico do endpoint |
| `422` | Validação da requisição falhou | Registrar e revisar parâmetros |
| `429` | Muitas requisições | Aplicar estratégia de rate limit |
| `5xx` | Erro do servidor | Avaliar retry com backoff |

O tratamento final será refinado durante a implementação da camada de resiliência.

---

# 10. Timeout

Todas as requisições realizadas pelo pipeline deverão possuir timeout explícito.

A implementação inicial do cliente utiliza:

```text
30 segundos
```

como timeout padrão do lado da aplicação.

O objetivo é evitar que uma execução permaneça indefinidamente aguardando uma resposta da API.

Fluxo esperado:

```text
Request
   │
   ▼
Wait for response
   │
   ├── Response received
   │       └── Continue
   │
   └── Timeout
           └── Retry / Failure
```

O timeout poderá posteriormente ser configurado externamente.

---

# 11. Retry e exponential backoff

Falhas transitórias não deverão provocar necessariamente a falha imediata de toda a ingestão.

Será implementada uma política de retry para situações específicas.

Exemplo conceitual:

```text
Request
   │
   ▼
Failure
   │
   ▼
Wait
   │
   ▼
Retry #1
   │
   ▼
Failure
   │
   ▼
Wait longer
   │
   ▼
Retry #2
```

O tempo entre tentativas deverá aumentar progressivamente utilizando **exponential backoff**.

O retry não será aplicado indiscriminadamente a qualquer erro.

Por exemplo:

```text
401 Unauthorized
```

normalmente indica um problema de autenticação e repetir a mesma requisição utilizando as mesmas credenciais não deverá resolver o problema.

Por outro lado, falhas transitórias de servidor e determinados cenários de rate limit poderão ser candidatos a retry.

---

# 12. Rate limit

A GitHub REST API aplica limites de requisições.

As respostas HTTP disponibilizam headers que permitem acompanhar o consumo do limite.

Os principais headers são:

```text
x-ratelimit-limit
x-ratelimit-remaining
x-ratelimit-used
x-ratelimit-reset
x-ratelimit-resource
```

Durante a exploração inicial, esses headers foram lidos diretamente pelo cliente.

Exemplo de comportamento observado:

```text
Limit:     5000
Remaining: 4990
Used:      10

Limit:     5000
Remaining: 4989
Used:      11

Limit:     5000
Remaining: 4988
Used:      12
```

Isso permitiu observar diretamente o consumo do limite a cada requisição realizada.

## 12.1 Tratamento do rate limit

Ao atingir determinados limites, a API pode responder com:

```http
403 Forbidden
```

ou:

```http
429 Too Many Requests
```

Por isso, o tratamento não deverá considerar apenas o status `429`.

Quando:

```text
x-ratelimit-remaining = 0
```

o pipeline deverá considerar:

```text
x-ratelimit-reset
```

para determinar quando novas requisições poderão ser realizadas.

Para determinados limites secundários, também poderá ser retornado:

```text
Retry-After
```

Fluxo conceitual:

```text
Request
   │
   ▼
403 / 429
   │
   ▼
Inspect Headers
   │
   ├── Retry-After
   │
   └── x-ratelimit-reset
   │
   ▼
Wait
   │
   ▼
Retry
```

Caso novas tentativas continuem sendo limitadas, será aplicado backoff progressivo e um limite máximo de tentativas.

---

# 13. Persistência Raw

As respostas originais da API serão preservadas antes das transformações.

Estrutura planejada:

```text
data/
└── raw/
    ├── repositories/
    ├── commits/
    ├── pull_requests/
    └── issues/
```

Uma possível organização por data de ingestão será:

```text
data/raw/commits/
└── ingestion_date=YYYY-MM-DD/
    ├── commits_001.json
    ├── commits_002.json
    └── commits_003.json
```

Além dos dados retornados pela API, poderão ser persistidos metadados da ingestão.

Exemplo conceitual:

```json
{
    "source": "github_api",
    "endpoint": "/repos/{owner}/{repo}/commits",
    "owner": "repository_owner",
    "repository": "repository_name",
    "ingestion_timestamp": "YYYY-MM-DDTHH:MM:SSZ",
    "status_code": 200,
    "records": []
}
```

A estrutura definitiva será validada durante a implementação.

---

# 14. Camada Silver

Após a persistência Raw, os dados serão processados e estruturados.

Fluxo:

```text
Raw JSON
   │
   ▼
Normalize / Flatten
   │
   ▼
Select Columns
   │
   ▼
Cast Data Types
   │
   ▼
Validate
   │
   ▼
Deduplicate
   │
   ▼
Silver
```

Estrutura planejada:

```text
data/
└── silver/
    ├── repositories/
    ├── commits/
    ├── pull_requests/
    └── issues/
```

O formato de persistência da camada Silver será definido durante a implementação, com preferência por um formato estruturado adequado para processamento analítico, como Parquet.

---

# 15. Incrementalidade

O pipeline não deverá consultar todo o histórico da API em todas as execuções quando o endpoint permitir uma estratégia incremental segura.

A ideia inicial é manter um checkpoint contendo informações da última execução concluída com sucesso.

Fluxo conceitual:

```text
Read checkpoint
       │
       ▼
last_successful_sync
       │
       ▼
GitHub API
       │
       ▼
Retrieve new/updated data
       │
       ▼
Raw
       │
       ▼
Process
       │
       ▼
Silver
       │
       ▼
Update checkpoint
```

O checkpoint somente deverá ser atualizado após a conclusão bem-sucedida da etapa correspondente.

## 15.1 Commits

A Commits API oferece os parâmetros:

```text
since
until
```

Isso permite limitar a consulta a um intervalo temporal.

Exemplo:

```http
GET /repos/{owner}/{repo}/commits?since=<last_successful_sync>
```

Essa será uma das estratégias avaliadas para a ingestão incremental de commits.

## 15.2 Issues

A API disponibiliza o parâmetro:

```text
since
```

para consultas de Issues, permitindo filtrar registros atualizados após determinado instante.

Isso torna possível avaliar uma estratégia como:

```http
GET /repos/{owner}/{repo}/issues?since=<last_successful_sync>
```

Como Issues existentes podem sofrer alterações, a estratégia deverá considerar tanto novos registros quanto atualizações.

## 15.3 Pull Requests

Para Pull Requests, a estratégia incremental será definida considerando os parâmetros disponíveis para ordenação e os campos temporais presentes nas respostas.

A implementação deverá considerar que uma Pull Request existente pode ser atualizada, fechada ou receber novas alterações após sua criação.

Por isso, a estratégia incremental poderá variar por entidade.

---

# 16. Deduplicação

Mesmo utilizando filtros incrementais, o pipeline deverá ser capaz de lidar com possíveis sobreposições entre execuções.

A camada de processamento deverá utilizar identificadores estáveis fornecidos pela API para identificar registros já processados.

Exemplo conceitual:

```text
API data
   +
Existing Silver
   │
   ▼
Identify key
   │
   ▼
Deduplicate / Update
   │
   ▼
Silver
```

Possíveis identificadores incluem:

```text
Repository  → id
Commit      → sha
Pull Request → id / number
Issue       → id / number
```

As chaves definitivas serão validadas individualmente para cada entidade.

---

# 17. Logs e observabilidade

O projeto utilizará logging estruturado em vez de depender de `print()` para acompanhamento das execuções.

Exemplos de eventos relevantes:

```text
INFO  Pipeline started
INFO  Requesting repository
INFO  Requesting commits page
INFO  HTTP request completed
WARN  Rate limit reached
INFO  Waiting before retry
INFO  Retry started
ERROR Request failed
INFO  Raw data persisted
INFO  Silver processing completed
INFO  Checkpoint updated
INFO  Pipeline completed
```

Sempre que possível, os logs deverão incluir contexto como:

- timestamp;
- endpoint;
- método HTTP;
- status code;
- número da página;
- quantidade de registros;
- número da tentativa;
- duração da requisição;
- owner;
- repository;
- rate limit remaining.

Tokens e outras credenciais nunca deverão aparecer nos logs.

---

# 18. Testes

O projeto deverá possuir testes automatizados para os principais componentes.

Estrutura inicialmente planejada:

```text
tests/
├── test_client.py
├── test_pagination.py
├── test_retry.py
└── test_processing.py
```

Alguns cenários que deverão ser testados:

- resposta `200`;
- resposta `401`;
- resposta `403`;
- resposta `404`;
- resposta `429`;
- resposta `5xx`;
- timeout;
- retry;
- limite máximo de tentativas;
- paginação com múltiplas páginas;
- ausência de `rel="next"`;
- transformação de JSON;
- deduplicação;
- tratamento de campos nulos;
- atualização do checkpoint;
- comportamento diante de rate limit.

Respostas simuladas da API poderão ser armazenadas em fixtures específicas para os testes.

Os testes manuais realizados durante a exploração inicial serão posteriormente substituídos por testes automatizados.

---

# 19. Estrutura planejada do projeto

```text
github-api-data-pipeline/
│
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
│
├── config/
│   └── config.yaml
│
├── data/
│   ├── raw/
│   │   ├── repositories/
│   │   ├── commits/
│   │   ├── pull_requests/
│   │   └── issues/
│   │
│   └── silver/
│       ├── repositories/
│       ├── commits/
│       ├── pull_requests/
│       └── issues/
│
├── logs/
│
├── notebooks/
│   └── test_api.py
│
├── src/
│   ├── api/
│   │   ├── client.py
│   │   ├── auth.py
│   │   └── pagination.py
│   │
│   ├── ingestion/
│   │   ├── repositories.py
│   │   ├── commits.py
│   │   ├── pull_requests.py
│   │   └── issues.py
│   │
│   ├── processing/
│   │   ├── repositories.py
│   │   ├── commits.py
│   │   ├── pull_requests.py
│   │   └── issues.py
│   │
│   ├── storage/
│   │   ├── raw.py
│   │   └── silver.py
│   │
│   └── utils/
│       ├── logger.py
│       └── exceptions.py
│
├── tests/
│   ├── test_client.py
│   ├── test_pagination.py
│   ├── test_retry.py
│   └── test_processing.py
│
└── docs/
    ├── architecture.md
    ├── api_exploration.md
    └── incremental_strategy.md
```

A estrutura poderá evoluir conforme o desenvolvimento avance.

O arquivo `notebooks/test_api.py` está sendo utilizado temporariamente para smoke tests durante a exploração inicial da API. Os testes permanentes deverão ser implementados posteriormente em `tests/`.

---

# 20. Componentes da camada API

A primeira implementação da camada de comunicação está organizada em:

```text
src/api/
├── auth.py
├── client.py
└── pagination.py
```

## 20.1 auth.py

Responsável por:

```text
.env
   │
   ▼
GITHUB_TOKEN
   │
   ▼
Authentication Headers
```

Os headers utilizados incluem:

```text
Authorization
Accept
X-GitHub-Api-Version
```

## 20.2 client.py

Responsável por:

- construção da URL;
- criação da sessão HTTP;
- envio dos headers;
- execução de requisições GET;
- envio de query parameters;
- timeout;
- retorno da resposta HTTP.

## 20.3 pagination.py

Responsável por:

- configurar `per_page`;
- realizar a primeira requisição;
- interpretar o header `Link`;
- localizar `rel="next"`;
- seguir a URL da próxima página;
- encerrar quando não existir próxima página.

Essa separação permite manter responsabilidades distintas entre autenticação, comunicação HTTP e navegação por resultados paginados.

---

# 21. Segurança

As seguintes práticas serão adotadas desde o início:

- tokens não serão versionados;
- `.env` será incluído no `.gitignore`;
- `.env.example` será mantido sem valores sensíveis;
- credenciais não serão incluídas em logs;
- tokens não serão hardcoded no código;
- somente as permissões necessárias deverão ser concedidas ao token;
- será utilizado Fine-grained Personal Access Token sempre que adequado;
- dados Raw serão mantidos fora do versionamento do Git.

---

# 22. Decisões iniciais

As principais decisões tomadas para o projeto são:

| Item | Decisão |
|---|---|
| API | GitHub REST API |
| Base URL | `https://api.github.com` |
| Versão | `2026-03-10` |
| Linguagem | Python |
| Biblioteca HTTP | `requests` |
| Operação inicial | HTTP GET |
| Autenticação | Fine-grained Personal Access Token |
| Header de autenticação | `Authorization: Bearer <token>` |
| Media type | `application/vnd.github+json` |
| Entidades iniciais | Repositories, Commits, Pull Requests e Issues |
| Paginação | Header `Link` |
| Próxima página | `rel="next"` |
| Página | Até 100 registros quando suportado |
| Timeout inicial | 30 segundos |
| Raw | Preservar resposta JSON |
| Silver | Dados normalizados e estruturados |
| Incrementalidade | Checkpoint + filtros específicos por entidade |
| Commits incremental | Avaliar `since` / `until` |
| Issues incremental | Avaliar `since` |
| Rate limit | Monitorar `x-ratelimit-*` e tratar `403` / `429` |
| Resiliência | Timeout + retry + exponential backoff |
| Observabilidade | Logging estruturado |
| Testes | Testes automatizados com respostas simuladas |
| Segredos | `.env`, nunca versionado |

---

# 23. Status da exploração

Até o momento foram concluídas as seguintes validações:

```text
Authentication
      │
      └── OK
          GET /user
          HTTP 200

Query Parameters
      │
      └── OK
          GET /user/repos
          per_page=5
          sort=updated

HTTP Headers
      │
      └── OK
          x-ratelimit-limit
          x-ratelimit-remaining
          x-ratelimit-used
          x-ratelimit-reset

Pagination
      │
      └── OK
          Link header
          rel="next"
          multiple pages
```

Com isso, a camada inicial:

```text
src/api/
```

está funcional para o escopo atual da exploração.

---

# 24. Próximos passos

Com a exploração inicial e a camada básica de comunicação concluídas, os próximos passos são:

1. consolidar a documentação da exploração da API;
2. iniciar a implementação de `src/ingestion/`;
3. implementar a ingestão de Repositories;
4. implementar a ingestão de Commits;
5. implementar a ingestão de Pull Requests;
6. implementar a ingestão de Issues;
7. persistir as respostas originais na camada Raw;
8. evoluir o cliente com tratamento explícito de respostas HTTP;
9. implementar retry e exponential backoff;
10. implementar tratamento de rate limit;
11. desenvolver a estratégia de carga incremental;
12. implementar processamento e camada Silver;
13. substituir smoke tests por testes automatizados;
14. adicionar logging estruturado;
15. consolidar a documentação técnica e arquitetura da solução.

A implementação será realizada de forma incremental para que a evolução do projeto demonstre claramente a aplicação dos conceitos estudados em integração com Web APIs.