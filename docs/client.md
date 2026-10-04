# Cliente da GitHub REST API

## Sobre

Este documento descreve a implementação e o comportamento do `GitHubClient`, cliente HTTP responsável pela comunicação entre o pipeline e a GitHub REST API.

O cliente centraliza as principais responsabilidades relacionadas à comunicação com a API, incluindo:

- autenticação;
- parâmetros de consulta;
- timeout das requisições;
- tratamento de respostas HTTP;
- exceções customizadas;
- mecanismos de retry;
- exponential backoff;
- tratamento de rate limit;
- header `Retry-After`;
- header `X-RateLimit-Reset`;
- geração de logs durante tentativas de retry.

O principal objetivo é fornecer uma camada HTTP reutilizável e resiliente para os módulos de ingestão, evitando que cada recurso do GitHub tenha que implementar individualmente autenticação, tratamento de erros, timeout e estratégias de retry.

---

# 1. Localização

O cliente está implementado em:

```text
src/api/client.py
```

Ele é utilizado pelos componentes de ingestão e paginação sempre que uma comunicação com a GitHub REST API é necessária.

O cliente possui dependências dos seguintes componentes:

```text
src/api/auth.py
src/utils/exceptions.py
src/utils/logger.py
```

Cada componente possui uma responsabilidade específica:

| Componente | Responsabilidade |
|---|---|
| `auth.py` | Criação dos headers de autenticação e configuração da GitHub API |
| `client.py` | Execução das requisições HTTP e controle de resiliência |
| `exceptions.py` | Definição das exceções customizadas da aplicação |
| `logger.py` | Configuração e persistência dos logs |

---

# 2. Responsabilidades do cliente

O `GitHubClient` funciona como a camada central de comunicação entre o pipeline e o GitHub.

Suas responsabilidades podem ser resumidas da seguinte forma:

```text
Ingestion / Pagination
         |
         v
    GitHubClient
         |
         +-- Construir URL
         +-- Adicionar autenticação
         +-- Enviar requisição HTTP
         +-- Aplicar timeout
         +-- Avaliar resposta
         |
         +-- Sucesso --------------------> Retornar resposta
         |
         +-- Falha temporária -----------> Retry
         |
         +-- Rate Limit -----------------> Aguardar + Retry
         |
         +-- Falha permanente -----------> Lançar exceção
         |
         +-- Evento de retry ------------> Registrar log
```

Com essa separação, os módulos de ingestão não precisam conhecer os detalhes relacionados à comunicação HTTP.

Por exemplo, o componente responsável pela ingestão de commits precisa apenas informar qual endpoint deve ser consultado. Ele não precisa implementar autenticação, timeout, retry, exponential backoff, rate limit ou classificação de erros HTTP.

---

# 3. Configuração

O cliente possui a seguinte configuração:

```python
GitHubClient(
    base_url=None,
    timeout=30,
    max_retries=3,
    backoff_factor=1.0
)
```

## 3.1 `base_url`

Define a URL base da GitHub REST API.

Quando nenhum valor é informado diretamente na criação do cliente, é utilizada a variável de ambiente:

```text
GITHUB_BASE_URL
```

Caso ela também não esteja disponível, o valor padrão é:

```text
https://api.github.com
```

O caractere `/` ao final da URL é removido quando necessário para evitar URLs malformadas durante a concatenação com os endpoints.

---

## 3.2 `timeout`

Define o tempo máximo permitido para uma requisição HTTP antes que ela seja considerada como timeout.

Valor padrão:

```text
30 segundos
```

Um timeout não encerra imediatamente a execução do pipeline.

Antes disso, o cliente aplica a estratégia de retry configurada.

---

## 3.3 `max_retries`

Define a quantidade máxima de novas tentativas permitidas após a requisição inicial.

Valor padrão:

```text
3 retries
```

Portanto:

```text
1 requisição inicial
        +
3 retries
        =
Máximo de 4 requisições
```

Caso a falha permaneça após todas as tentativas, a exceção correspondente é lançada.

---

## 3.4 `backoff_factor`

Define o fator utilizado no cálculo do exponential backoff entre as tentativas.

Valor padrão:

```text
1.0
```

O tempo de espera é calculado utilizando:

```text
backoff_factor * (2 ** attempt)
```

Com a configuração padrão:

```text
Tentativa 0 -> 1 segundo
Tentativa 1 -> 2 segundos
Tentativa 2 -> 4 segundos
```

---

# 4. Autenticação

A autenticação não é implementada diretamente dentro do `GitHubClient`.

Os headers são fornecidos pelo componente:

```text
src/api/auth.py
```

Durante a inicialização, o cliente cria uma sessão reutilizável:

```python
self.session = requests.Session()
```

e adiciona os headers de autenticação:

```python
self.session.headers.update(
    get_auth_headers()
)
```

O token de acesso é obtido por variável de ambiente, evitando que credenciais sejam armazenadas diretamente no código-fonte.

A sessão também permite reutilizar a configuração HTTP entre diferentes requisições realizadas pelo pipeline.

---

# 5. Métodos de requisição

O cliente disponibiliza dois métodos públicos para execução de requisições.

## 5.1 `get()`

O método `get()` recebe um endpoint da GitHub REST API.

Exemplo:

```python
client.get(
    endpoint="/repos/owner/repository"
)
```

O endpoint é combinado com a URL base configurada.

Exemplo:

```text
Base URL:
https://api.github.com

Endpoint:
/repos/owner/repository

URL final:
https://api.github.com/repos/owner/repository
```

O método também aceita parâmetros opcionais:

```python
client.get(
    endpoint="/user/repos",
    params={
        "per_page": 100,
        "sort": "updated"
    }
)
```

---

## 5.2 `get_url()`

O método `get_url()` recebe uma URL completa em vez de um endpoint.

Exemplo:

```python
client.get_url(next_url)
```

Esse método é utilizado principalmente pelo componente de paginação, pois o GitHub pode fornecer a URL da próxima página por meio do header HTTP `Link`.

Tanto `get()` quanto `get_url()` delegam a execução efetiva da requisição para o método interno `_request()`.

---

# 6. Fluxo de uma requisição

O método `_request()` concentra a principal lógica de resiliência do cliente.

O fluxo simplificado é:

```text
Requisição HTTP
      |
      v
requests.Session.get()
      |
      +--------------------------+
      |                          |
      v                          v
   Resposta                  Exceção
      |                          |
      |                  +-------+-------+
      |                  |               |
      |               Timeout       ConnectionError
      |                  |               |
      |                  +-------+-------+
      |                          |
      |                          v
      |                 Exponential Backoff
      |                          |
      |                         Log
      |                          |
      |                        Retry
      |
      v
Avaliar resposta HTTP
      |
      +-- Rate Limit -------> Espera -> Log -> Retry
      |
      +-- 500/502/503 ------> Backoff -> Log -> Retry
      |
      +-- Outros erros -----> Exceção customizada
      |
      +-- 2xx --------------> Retornar resposta
```

---

# 7. Tratamento das respostas HTTP

As respostas HTTP são classificadas pelo método `_handle_response()`.

## 7.1 Respostas de sucesso

Qualquer status entre:

```text
200-299
```

é considerado bem-sucedido.

A resposta é retornada ao componente responsável pela chamada para que os dados possam ser processados.

---

## 7.2 HTTP 400

Um `400 Bad Request` representa uma requisição inválida.

Exceção utilizada:

```text
BadRequestError
```

Exemplo:

```text
GitHub API error [400]: Invalid request.
```

Esse tipo de erro não gera retry.

---

## 7.3 HTTP 401

Um `401 Unauthorized` representa falha de autenticação.

Exceção:

```text
AuthenticationError
```

Exemplo:

```text
GitHub API error [401]: Authentication failed.
```

Esse erro também não gera retry automático.

---

## 7.4 HTTP 403

O status `403 Forbidden` pode representar duas situações diferentes.

O cliente verifica o header:

```text
X-RateLimit-Remaining
```

Quando:

```text
X-RateLimit-Remaining = 0
```

a resposta é interpretada como rate limit.

Caso contrário, ela é tratada como problema de acesso ou autorização.

As possíveis exceções são:

```text
RateLimitError
AuthenticationError
```

---

## 7.5 HTTP 404

Um `404 Not Found` indica que o recurso solicitado não foi encontrado.

Exceção:

```text
ResourceNotFoundError
```

Exemplo:

```text
GitHub API error [404]: Resource not found.
```

O cliente não realiza retry para esse status.

---

## 7.6 HTTP 429

Um `429 Too Many Requests` é interpretado como rate limit.

Antes de lançar uma exceção, o cliente tenta determinar quanto tempo deve aguardar e executa novamente a requisição.

Caso todas as tentativas sejam esgotadas, é lançada:

```text
RateLimitError
```

---

## 7.7 Erros de servidor

Os seguintes erros temporários de servidor são considerados elegíveis para retry:

```text
500
502
503
```

Eles estão definidos em:

```python
RETRYABLE_STATUS_CODES = {
    500,
    502,
    503,
}
```

Para esses erros, o cliente utiliza exponential backoff antes de realizar uma nova tentativa.

Caso o número máximo de retries seja atingido, é lançada:

```text
ServerError
```

---

# 8. Estratégia de Retry

Retries são realizados somente para condições consideradas temporárias ou potencialmente recuperáveis.

| Condição | Retry |
|---|---|
| HTTP 500 | Sim |
| HTTP 502 | Sim |
| HTTP 503 | Sim |
| HTTP 429 | Sim |
| HTTP 403 causado por rate limit | Sim |
| Timeout | Sim |
| Connection error | Sim |
| HTTP 400 | Não |
| HTTP 401 | Não |
| HTTP 403 sem rate limit | Não |
| HTTP 404 | Não |

Essa distinção evita novas tentativas desnecessárias para erros que dificilmente serão resolvidos sem alguma alteração na requisição, nas permissões ou nas credenciais.

---

# 9. Exponential Backoff

Falhas temporárias utilizam exponential backoff.

A fórmula utilizada é:

```text
wait_time = backoff_factor * (2 ** attempt)
```

Considerando:

```text
backoff_factor = 1.0
max_retries = 3
```

o fluxo será:

```text
Requisição inicial
       |
       X
       |
   aguarda 1s
       |
    Retry 1
       |
       X
       |
   aguarda 2s
       |
    Retry 2
       |
       X
       |
   aguarda 4s
       |
    Retry 3
```

Esse comportamento evita que o cliente envie repetidamente novas requisições de forma imediata após uma falha temporária.

A lógica está centralizada no método:

```text
_wait_before_retry()
```

---

# 10. Tratamento de Timeout

Todas as requisições utilizam o timeout configurado no cliente:

```python
self.session.get(
    url=url,
    params=params,
    timeout=self.timeout
)
```

Quando a biblioteca `requests` lança:

```text
requests.exceptions.Timeout
```

o cliente verifica se ainda existem tentativas disponíveis.

O fluxo é:

```text
Timeout
   |
   v
Verificar limite de retries
   |
   +-- Limite atingido --> RequestTimeoutError
   |
   +-- Retry disponível
             |
             v
      Calcular backoff
             |
             v
      Registrar log
             |
             v
          Aguardar
             |
             v
           Retry
```

Caso todas as tentativas falhem:

```text
RequestTimeoutError
```

é lançada.

---

# 11. Tratamento de Erros de Conexão

Falhas de conexão são tratadas separadamente das respostas HTTP.

Quando ocorre:

```text
requests.exceptions.ConnectionError
```

o cliente aplica a mesma estratégia de exponential backoff utilizada para erros temporários de servidor.

Fluxo:

```text
ConnectionError
       |
       v
Verificar limite de retries
       |
       +-- Limite atingido --> GitHubConnectionError
       |
       +-- Retry disponível
                  |
                  v
          Exponential Backoff
                  |
                  v
                 Log
                  |
                  v
                Retry
```

Se todas as tentativas falharem, é lançada:

```text
GitHubConnectionError
```

---

# 12. Tratamento de Rate Limit

O rate limit exige uma estratégia diferente de espera, pois a resposta da API pode fornecer informações indicando quando uma nova requisição deve ser realizada.

O cliente identifica rate limit nas seguintes situações:

```text
HTTP 429
```

ou:

```text
HTTP 403
+
X-RateLimit-Remaining = 0
```

A prioridade para determinar o tempo de espera é:

```text
1. Retry-After
2. X-RateLimit-Reset
3. Exponential Backoff
```

Essa lógica está implementada em:

```text
_get_rate_limit_wait_time()
```

---

## 12.1 `Retry-After`

Quando a resposta contém:

```text
Retry-After
```

o valor é interpretado como a quantidade de segundos que o cliente deve aguardar.

Exemplo:

```text
HTTP 429
Retry-After: 5
```

Resultado:

```text
Aguardar 5 segundos
        |
        v
Executar novo request
```

Na implementação atual, `Retry-After` possui a maior prioridade para determinação do tempo de espera.

---

## 12.2 `X-RateLimit-Reset`

Quando `Retry-After` não está disponível, o cliente procura:

```text
X-RateLimit-Reset
```

O valor é interpretado como um Unix timestamp.

O tempo de espera é calculado como:

```text
X-RateLimit-Reset - horário atual
```

Exemplo:

```text
Horário atual:
1000

X-RateLimit-Reset:
1010

Tempo de espera:
10 segundos
```

Para evitar valores negativos, o cliente utiliza:

```text
max(tempo_calculado, 0)
```

---

## 12.3 Fallback do Rate Limit

Caso nem:

```text
Retry-After
```

nem:

```text
X-RateLimit-Reset
```

possam ser utilizados, o cliente utiliza exponential backoff como fallback.

Exemplo:

```text
HTTP 429
    |
    | Retry-After indisponível
    |
    | X-RateLimit-Reset indisponível
    |
    v
Exponential Backoff
    |
    +-- 1 segundo
    +-- 2 segundos
    +-- 4 segundos
```

Dessa forma, o cliente continua possuindo uma estratégia de retry mesmo quando a API não informa explicitamente quanto tempo deve ser aguardado.

---

# 13. Logging

Os eventos relacionados aos retries são registrados utilizando:

```text
src/utils/logger.py
```

O cliente utiliza o nível:

```text
WARNING
```

para registrar:

```text
Erros temporários de servidor
Timeout
Erros de conexão
Rate limit
```

Exemplo de erro temporário de servidor:

```text
WARNING | src.api.client | GitHub API temporary server error. HTTP 503. Retry 1/3 in 1.00 seconds.
```

Exemplo de timeout:

```text
WARNING | src.api.client | GitHub API request timeout. Retry 1/3 in 1.00 seconds.
```

Exemplo de erro de conexão:

```text
WARNING | src.api.client | GitHub API connection error. Retry 1/3 in 1.00 seconds.
```

Exemplo de rate limit:

```text
WARNING | src.api.client | GitHub API rate limit reached. HTTP 429. Retry 1/3 in 5.00 seconds.
```

Os logs são persistidos em:

```text
logs/github_api.log
```

Informações sensíveis, como tokens de autenticação, não são incluídas nas mensagens de log.

---

# 14. Exceções Customizadas

O cliente utiliza exceções específicas da aplicação definidas em:

```text
src/utils/exceptions.py
```

A estrutura atual inclui:

```text
GitHubAPIError
|
+-- BadRequestError
|
+-- AuthenticationError
|
+-- ResourceNotFoundError
|
+-- RateLimitError
|
+-- ServerError
|
+-- RequestTimeoutError
|
+-- GitHubConnectionError
```

O uso dessas exceções permite que outros componentes do pipeline diferenciem os diferentes tipos de falha sem depender diretamente das exceções internas da biblioteca `requests` ou da análise manual dos status HTTP.

---

# 15. Fluxo de Resiliência

O comportamento geral do cliente pode ser representado da seguinte maneira:

```text
                         REQUEST
                            |
                            v
                     GitHub REST API
                            |
          +-----------------+-----------------+
          |                                   |
          v                                   v
    Exceção de rede                         Resposta
          |                                   |
     +----+----+                   +----------+----------+
     |         |                   |                     |
  Timeout   Connection          Rate Limit          Outros HTTP
     |         |                   |                     |
     +----+----+             +-----+-----+         +-----+-----+
          |                  |           |         |           |
          v              Retry-After   Reset      2xx       4xx/5xx
      Backoff                |           |         |           |
          |                  +-----+-----+         |      +----+----+
          v                        |               |      |         |
         Log                       v               |    5xx      Outros
          |                     Aguardar           |      |         |
          v                        |               |   Backoff   Exceção
        Retry                     Log              |      |
                                   |               |     Log
                                   v               |      |
                                 Retry             |    Retry
                                                   |
                                                   v
                                                Retorno
```

---

# 16. Validação

Os mecanismos de resiliência foram validados utilizando respostas HTTP e exceções simuladas.

Foram testados os seguintes cenários:

```text
1. HTTP 503 temporário seguido de HTTP 200
2. Timeout seguido de HTTP 200
3. ConnectionError seguido de HTTP 200
4. HTTP 429 com Retry-After seguido de HTTP 200
5. HTTP 403 com X-RateLimit-Remaining = 0
   e X-RateLimit-Reset seguido de HTTP 200
6. HTTP 429 sem headers de tempo para rate limit
7. HTTP 503 persistente até atingir o máximo de retries
8. HTTP 429 persistente até atingir o máximo de retries
```

Os seguintes comportamentos foram validados:

```text
Server Error:
503 -> 503 -> 200
Espera: 1s -> 2s

Timeout:
Timeout -> Timeout -> 200
Espera: 1s -> 2s

Connection:
ConnectionError -> ConnectionError -> 200
Espera: 1s -> 2s

Retry-After:
429 -> 200
Espera: 5s

X-RateLimit-Reset:
403 -> 200
Espera calculada: 10s

Rate Limit Fallback:
429 -> 429 -> 200
Espera: 1s -> 2s
```

O comportamento de limite máximo de retries também foi validado.

Com:

```text
max_retries = 3
```

a quantidade máxima de requisições é:

```text
1 requisição inicial + 3 retries = 4 requisições
```

Após a última tentativa sem sucesso, a exceção correspondente é lançada.

---

# 17. Capacidades Atuais

A implementação atual do `GitHubClient` possui:

```text
Autenticação                  Implementado
Parâmetros de consulta        Implementado
Sessão HTTP reutilizável      Implementado
Construção de URL             Implementado
Requisição por URL completa   Implementado

Request timeout               Implementado
Classificação de erros HTTP   Implementado
Exceções customizadas         Implementado

Retry 500/502/503             Implementado
Retry de timeout              Implementado
Retry de conexão              Implementado
Exponential backoff           Implementado
Limite máximo de retries      Implementado

Rate limit HTTP 429           Implementado
Rate limit HTTP 403           Implementado
Retry-After                   Implementado
X-RateLimit-Reset             Implementado
Fallback de rate limit        Implementado

Logging de retries            Implementado
```

---

# 18. Papel no Pipeline

O cliente fornece a base de comunicação utilizada pela camada de ingestão.

O fluxo atual pode ser representado como:

```text
GitHub REST API
       ^
       |
 GitHubClient
       ^
       |
 +-----+------------------+
 |        |        |      |
Repository Commits Pulls Issues
              ^
              |
        GitHubPaginator
```

Os componentes de ingestão são responsáveis por definir quais recursos do GitHub devem ser consultados.

O `GitHubClient` é responsável por garantir que essas requisições sejam realizadas de forma centralizada e resiliente.

Essa separação permite que as próximas etapas do pipeline sejam desenvolvidas sem duplicar regras de comunicação HTTP, autenticação ou tratamento de falhas.

---

# 19. Próximas Etapas

Com o cliente HTTP e a camada de resiliência concluídos, as próximas etapas do desenvolvimento serão:

```text
GitHub REST API
       |
       v
GitHubClient                  Concluído
       |
       v
Ingestion                     Concluído
       |
       v
Persistência Raw / JSON       Próxima etapa
       |
       v
Metadados de ingestão
       |
       v
Estratégia incremental
       |
       v
Processamento
       |
       v
Silver / Dados estruturados
```

O `GitHubClient` continuará sendo o componente central de comunicação HTTP, enquanto as próximas etapas serão responsáveis pela persistência dos dados, controle de incrementalidade, transformação, validação e armazenamento estruturado.