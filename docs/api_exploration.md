
# Exploração da API REST do GitHub

## Sobre

Este documento reúne os principais conceitos e resultados da exploração da API REST do GitHub utilizada no projeto GitHub API Data Pipeline.

O estudo contempla:

- Estrutura das requisições HTTP.
- Autenticação.
- Endpoints.
- Parâmetros.
- Paginação.
- Rate limits.
- Respostas JSON.
- Estratégias de ingestão.

---

# 1. Introdução

A API REST do GitHub permite acessar informações de usuários, repositórios, commits, issues, pull requests e outros recursos.

A comunicação ocorre por meio do protocolo HTTPS.

A URL base utilizada é:

```text
https://api.github.com
```

As requisições retornam dados estruturados, geralmente em JSON.

---

# 2. Autenticação

O projeto utiliza autenticação por token de acesso pessoal.

O token é enviado no cabeçalho HTTP:

```http
Authorization: Bearer <TOKEN>
```

O token é carregado por meio da configuração local do projeto.

A utilização de variáveis de ambiente evita a inclusão direta das credenciais no código-fonte.

## 2.1 Segurança

Boas práticas:

- Não inserir tokens diretamente no código.
- Não publicar o arquivo `.env`.
- Utilizar permissões mínimas necessárias.
- Revogar tokens comprometidos.
- Evitar registrar credenciais nos logs.

---

# 3. Endpoints explorados

## 3.1 Usuário autenticado

```http
GET /user
```

Retorna informações sobre o usuário associado ao token.

Foi utilizado para validar a autenticação.

## 3.2 Repositórios do usuário autenticado

```http
GET /user/repos
```

Retorna repositórios acessíveis ao usuário autenticado, de acordo com os parâmetros e permissões utilizados.

Exemplo:

```http
GET /user/repos?per_page=5&sort=updated
```

## 3.3 Repositórios de um usuário

```http
GET /users/{username}/repos
```

Permite consultar repositórios públicos de um usuário.

Exemplo:

```http
GET /users/milenoepifanio/repos
```

## 3.4 Commits

```http
GET /repos/{owner}/{repo}/commits
```

Retorna commits associados ao repositório.

Parâmetros relevantes:

- `sha`: referência de branch, tag ou commit.
- `path`: filtro por caminho.
- `since`: limite temporal inferior.
- `until`: limite temporal superior.
- `per_page`: quantidade de registros por página.
- `page`: número da página.

## 3.5 Issues

```http
GET /repos/{owner}/{repo}/issues
```

Retorna issues associadas ao repositório.

Parâmetros relevantes:

- `state`: estado das issues.
- `since`: referência de atualização.
- `sort`: campo de ordenação.
- `direction`: direção da ordenação.
- `per_page`: quantidade por página.
- `page`: página solicitada.

**Observação:** o endpoint de issues também pode retornar pull requests, identificáveis pela presença do campo `pull_request`.

## 3.6 Pull Requests

```http
GET /repos/{owner}/{repo}/pulls
```

Retorna pull requests do repositório.

Parâmetros relevantes:

- `state`: estado dos pull requests.
- `sort`: critério de ordenação.
- `direction`: direção.
- `per_page`: quantidade por página.
- `page`: página solicitada.

A listagem de pull requests não utiliza o mesmo parâmetro incremental `since` disponibilizado pelos endpoints de commits e issues.

Por isso, o controle incremental depende da lógica implementada pelo pipeline.

---

# 4. Paginação

A API do GitHub utiliza paginação para dividir grandes conjuntos de resultados.

O parâmetro `per_page` controla a quantidade de registros solicitada por página, respeitando os limites do endpoint.

O parâmetro `page` permite solicitar uma página específica.

Exemplo:

```http
GET /user/repos?per_page=5&page=1
```

## 4.1 Cabeçalho Link

Quando aplicável, a API retorna um cabeçalho HTTP semelhante a:

```http
Link: <https://api.github.com/user/repos?page=2>; rel="next"
```

O atributo `rel="next"` identifica a próxima página.

O módulo de paginação utiliza essas informações para continuar a extração.

## 4.2 Fluxo de paginação

```text
Primeira requisição
        |
        v
Receber registros
        |
        v
Verificar cabeçalho Link
        |
        +---- Existe next? ---- Não ----> Encerrar
        |
       Sim
        |
        v
Consultar próxima página
        |
        v
Acumular registros
        |
        v
Repetir
```

Durante a exploração inicial, foi validada a recuperação de três páginas com cinco registros por página.

---

# 5. Rate limits

A API do GitHub estabelece limites de requisições para proteger seus serviços.

Os limites variam conforme o tipo de autenticação, endpoint e contexto de utilização.

Os cabeçalhos relevantes incluem:

| Cabeçalho | Descrição |
|---|---|
| X-RateLimit-Limit | Limite aplicável |
| X-RateLimit-Remaining | Requisições restantes |
| X-RateLimit-Used | Requisições utilizadas |
| X-RateLimit-Reset | Momento de redefinição do limite |
| Retry-After | Tempo recomendado de espera, quando informado |

O GitHub também utiliza mecanismos de limitação secundária.

## 5.1 Estratégia implementada

O cliente HTTP identifica respostas associadas a rate limits e calcula um período de espera antes de uma nova tentativa.

A estratégia considera:

1. `Retry-After`, quando disponível.
2. `X-RateLimit-Reset`, quando aplicável.
3. Backoff exponencial como alternativa.

A recuperação respeita um tempo máximo de espera configurado.

Quando a espera necessária ultrapassa esse limite, o cliente informa a falha em vez de aguardar indefinidamente.

---

# 6. Tratamento de respostas HTTP

| Código | Interpretação |
|---|---|
| 200 | Requisição bem-sucedida |
| 400 | Requisição inválida |
| 401 | Falha de autenticação |
| 403 | Acesso negado ou possível limitação |
| 404 | Recurso não encontrado |
| 429 | Excesso de requisições |
| 500 | Erro interno do servidor |
| 502 | Falha de gateway |
| 503 | Serviço indisponível |
| 504 | Timeout de gateway |

O cliente diferencia falhas recuperáveis e não recuperáveis.

Nem toda resposta HTTP 403 representa rate limit.

---

# 7. Estrutura dos dados

Os recursos retornam objetos JSON com estruturas específicas.

## 7.1 Commits

Campos relevantes:

- `sha`
- `commit.message`
- `commit.author.date`
- `commit.committer.date`
- `author.login`
- `html_url`

## 7.2 Repositories

Campos relevantes:

- `id`
- `name`
- `full_name`
- `owner.login`
- `description`
- `private`
- `fork`
- `archived`
- `language`
- `created_at`
- `updated_at`
- `pushed_at`

## 7.3 Issues

Campos relevantes:

- `id`
- `number`
- `title`
- `state`
- `state_reason`
- `user.login`
- `labels`
- `created_at`
- `updated_at`
- `closed_at`

## 7.4 Pull Requests

Campos relevantes:

- `id`
- `number`
- `title`
- `state`
- `draft`
- `user.login`
- `base.ref`
- `head.ref`
- `created_at`
- `updated_at`
- `merged_at`

---

# 8. Estratégia de persistência

O projeto armazena os dados em dois formatos.

### JSON

Preserva os registros completos recebidos da API.

### Parquet

Armazena campos selecionados, com estrutura tabular e conversão de datas quando aplicável.

Essa separação permite manter os dados originais disponíveis para futuras transformações.

---

# 9. Resultados da exploração

Durante o desenvolvimento, foram validados:

- Autenticação com token.
- Consulta ao usuário autenticado.
- Consulta a repositórios.
- Paginação de resultados.
- Leitura de cabeçalhos de rate limit.
- Recuperação de commits.
- Recuperação de issues.
- Recuperação de pull requests.
- Persistência dos dados em JSON e Parquet.

Essas validações fundamentaram a implementação do pipeline.

---

# 10. Referências

- [Documentação da API REST do GitHub](https://docs.github.com/en/rest)
- [Autenticação na API REST](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
- [Paginação](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
- [Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

---

# 11. Documentos relacionados

- [README](../README.md)
- [Arquitetura](architecture.md)
- [Cliente HTTP](client.md)
- [Estratégia Incremental](incremental_strategy.md)
