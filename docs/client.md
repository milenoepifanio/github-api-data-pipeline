
# Cliente HTTP e Recuperação de Falhas

## Sobre

Este documento descreve o cliente HTTP utilizado pelo GitHub API Data Pipeline.

O componente foi desenvolvido para centralizar a comunicação com a API REST do GitHub, garantindo reutilização, padronização e maior confiabilidade nas requisições.

O cliente implementa:

- Autenticação.
- Configuração de timeout.
- Validação de URLs.
- Tratamento de respostas HTTP.
- Retry.
- Backoff exponencial.
- Tratamento de rate limits.
- Registro de logs operacionais.

---

# 1. Localização

O cliente está implementado em:

```text
src/api/client.py
```

A classe principal é:

```python
GitHubClient
```

O módulo utiliza os cabeçalhos de autenticação disponibilizados por:

```text
src/api/auth.py
```

---

# 2. Responsabilidades

O cliente HTTP é responsável por executar requisições e tratar falhas de comunicação.

As regras de negócio de cada recurso permanecem nos módulos de ingestão.

Essa separação permite reutilizar o mesmo cliente para commits, repositories, issues e pull requests.

---

# 3. Configuração

A classe `GitHubClient` possui parâmetros de configuração para controle das requisições.

| Parâmetro | Valor padrão | Descrição |
|---|---|---|
| base_url | URL base configurada | Endereço base da API |
| timeout | 30 segundos | Tempo máximo de espera da requisição |
| max_retries | 3 | Número de tentativas adicionais |
| backoff_factor | 1.0 | Fator de espera exponencial |
| max_retry_wait | 60 segundos | Tempo máximo permitido por espera |

O cliente valida os parâmetros de configuração para evitar valores inválidos.

---

# 4. Métodos principais

## 4.1 get()

Executa uma requisição GET utilizando um endpoint relativo à URL base.

Exemplo de utilização:

```python
response = client.get(
    endpoint="/user"
)
```

O método aceita parâmetros de consulta.

## 4.2 get_url()

Executa uma requisição GET utilizando uma URL completa.

Esse método é especialmente útil para paginação, quando a API fornece a URL da próxima página no cabeçalho `Link`.

Antes da requisição, a URL é validada.

## 4.3 _request()

Centraliza a execução HTTP.

Esse método coordena:

1. Validação da URL.
2. Envio da requisição.
3. Verificação da resposta.
4. Identificação de falhas recuperáveis.
5. Cálculo do tempo de espera.
6. Nova tentativa, quando permitida.
7. Retorno da resposta ou propagação da exceção.

---

# 5. Timeout

O timeout define o tempo máximo de espera configurado para uma requisição.

Quando ocorre uma exceção de timeout, o cliente pode realizar novas tentativas.

Se todas as tentativas forem esgotadas, a falha é propagada como uma exceção específica.

Essa estratégia evita que falhas transitórias interrompam imediatamente o processamento.

---

# 6. Retry

Retry representa a repetição de uma requisição após uma falha potencialmente temporária.

O cliente permite novas tentativas para:

- Timeout.
- Falhas de conexão.
- HTTP 500.
- HTTP 502.
- HTTP 503.
- HTTP 504.
- HTTP 429.
- HTTP 403 quando identificado como rate limit.

O parâmetro `max_retries` representa tentativas adicionais.

Por exemplo:

```text
max_retries = 3
```

Permite até quatro tentativas no total:

```text
Tentativa inicial
      |
      v
Retry 1
      |
      v
Retry 2
      |
      v
Retry 3
```

A execução termina quando uma resposta válida é recebida ou quando as tentativas são esgotadas.

---

# 7. Backoff exponencial

O backoff exponencial aumenta progressivamente o intervalo entre tentativas.

A estratégia reduz a pressão sobre a API durante falhas temporárias.

O tempo de espera segue uma progressão baseada no fator configurado.

Exemplo com fator 1:

| Retry | Espera |
|---|---|
| 1 | 1 segundo |
| 2 | 2 segundos |
| 3 | 4 segundos |

O intervalo é limitado pelo parâmetro `max_retry_wait`.

---

# 8. Tratamento de rate limits

A API do GitHub pode limitar temporariamente a quantidade ou a frequência das requisições.

O cliente identifica cenários relacionados a:

- Limites primários.
- Limites secundários.
- HTTP 429.
- HTTP 403 com indicadores de limitação.

## 8.1 Cálculo da espera

O cliente considera as informações retornadas pela API.

A prioridade é:

1. Cabeçalho `Retry-After`.
2. Cabeçalho `X-RateLimit-Reset`.
3. Backoff exponencial.

Quando a espera necessária ultrapassa `max_retry_wait`, o cliente gera uma exceção específica.

Isso impede períodos de espera excessivos em uma única tentativa.

## 8.2 Diferenciação de HTTP 403

Nem toda resposta HTTP 403 indica limitação de requisições.

O cliente utiliza cabeçalhos e mensagens retornadas pela API para diferenciar um bloqueio de acesso de um cenário de rate limit.

Uma resposta HTTP 403 sem indicadores de limitação não deve ser repetida automaticamente.

---

# 9. Tratamento de exceções

As exceções personalizadas estão definidas em:

```text
src/utils/exceptions.py
```

| Exceção | Responsabilidade |
|---|---|
| GitHubAPIError | Exceção base |
| BadRequestError | Requisição inválida |
| AuthenticationError | Problema de autenticação ou autorização |
| ResourceNotFoundError | Recurso não encontrado |
| RateLimitError | Limitação de requisições |
| ServerError | Erro de servidor |
| RequestTimeoutError | Timeout |
| GitHubConnectionError | Falha de conexão |

A utilização de exceções específicas facilita a identificação da origem dos problemas.

---

# 10. Validação de URLs

O cliente valida URLs completas antes de executar requisições.

As verificações incluem:

- Utilização de HTTPS.
- Correspondência com o host configurado.
- Ausência de credenciais embutidas na URL.
- Ausência de fragmentos.
- Respeito ao caminho base configurado.

Essa proteção é importante porque URLs de paginação são obtidas a partir de respostas externas.

O cliente também desabilita o acompanhamento automático de redirecionamentos.

---

# 11. Observabilidade

O cliente registra eventos relevantes durante a comunicação HTTP.

Os logs incluem:

- Tentativas de recuperação.
- Código HTTP relacionado à falha.
- Tempo de espera.
- Recuperação bem-sucedida.
- Esgotamento de tentativas.
- Excesso do limite máximo de espera.

Exemplo:

```text
WARNING | Retryable HTTP response | HTTP=503 | Retry=1/2 | Wait=1.00s

INFO | GitHub API request recovered | HTTP=200 | Retries=1
```

Os logs ajudam a distinguir falhas transitórias de falhas definitivas.

---

# 12. Testes de recuperação

Os testes estão implementados em:

```text
notebooks/test_client_recovery.py
```

Foram validados os seguintes cenários:

| Cenário | Resultado |
|---|---|
| HTTP 401 sem retry | OK |
| HTTP 403 sem rate limit | OK |
| HTTP 503 com recuperação | OK |
| Timeout com tentativas esgotadas | OK |
| Rate limit secundário com recuperação | OK |
| Espera superior ao máximo permitido | OK |
| Bloqueio de URL de paginação insegura | OK |
| Rejeição de configuração inválida | OK |

Os testes utilizam simulações de respostas e falhas, evitando depender de erros reais da API.

Após essas verificações, o cliente também foi validado em uma execução integrada do pipeline.

---

# 13. Limitações

O cliente utiliza uma estratégia de recuperação baseada em regras definidas.

Não implementa:

- Circuit breaker.
- Fila persistente de requisições.
- Controle distribuído de rate limit.
- Cache HTTP persistente.
- Métricas centralizadas.
- Alertas automáticos.

Esses recursos podem ser incorporados em evoluções futuras.

---

# 14. Documentos relacionados

- [README](../README.md)
- [Arquitetura](architecture.md)
- [Exploração da API](api_exploration.md)
- [Estratégia Incremental](incremental_strategy.md)
