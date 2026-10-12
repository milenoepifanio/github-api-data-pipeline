# Referência Técnica da Integração com a API REST do GitHub

> **Finalidade:** guia de estudo, manutenção e comprovação técnica da competência **Hard Skills — API: Integração com Web APIs**. Este documento identifica o que foi implementado, por que foi implementado, como validar e onde encontrar o código.
>
> **Importante sobre linhas:** os números de linha são exatos **somente para o arquivo `resources.py` disponibilizado durante o desenvolvimento**, identificado nesta referência como *versão consultada*. Para os demais arquivos, não foi disponibilizada uma cópia integral e atual da branch; portanto, são indicados os métodos e comandos para obter os números exatos, sem presumir posições no código.

## 1. Mapa de leitura

| Assunto | Arquivo | Ponto de entrada / implementação |
|---|---|---|
| Visão geral e execução | [`src/pipeline/main.py`](../src/pipeline/main.py) | Orquestração principal |
| Autenticação por token | [`src/api/auth.py`](../src/api/auth.py) | Carregamento do token e cabeçalhos |
| HTTP, timeout, retries, rate limit | [`src/api/client.py`](../src/api/client.py) | Classe `GitHubClient`; métodos `get`, `get_url`, `_request` |
| Paginação | [`src/api/pagination.py`](../src/api/pagination.py) | Classe `GitHubPaginator`; interpretação de `Link` |
| Erros específicos | [`src/utils/exceptions.py`](../src/utils/exceptions.py) | Hierarquia de exceções |
| Extração de commits | [`src/ingestion/commits.py`](../src/ingestion/commits.py) | Endpoint de commits |
| Extração de repositórios | [`src/ingestion/repositories.py`](../src/ingestion/repositories.py) | Endpoint de repositórios |
| Extração de issues | [`src/ingestion/issues.py`](../src/ingestion/issues.py) | Endpoint de issues |
| Extração de PRs | [`src/ingestion/pull_requests.py`](../src/ingestion/pull_requests.py) | Endpoint de pull requests |
| Fluxo incremental de commits | [`src/pipeline/commits.py`](../src/pipeline/commits.py) | Checkpoint, filtro e persistência |
| Recursos e mudanças | [`src/pipeline/resources.py`](../src/pipeline/resources.py) | `ResourcesPipeline` |
| Raw JSON e Parquet | [`src/storage/raw.py`](../src/storage/raw.py) | `RawStorage` |
| Checkpoints básicos | [`src/utils/checkpoint.py`](../src/utils/checkpoint.py) | `CheckpointManager.load` e `save` |
| Logs | [`src/utils/logger.py`](../src/utils/logger.py) | Configuração dos handlers |
| Testes de resiliência | [`notebooks/test_client_recovery.py`](../notebooks/test_client_recovery.py) | Oito cenários simulados |
| Testes de eventos | [`notebooks/test_repository_changes.py`](../notebooks/test_repository_changes.py) | Estados e idempotência |
| Integridade Raw | [`notebooks/test_raw_integrity.py`](../notebooks/test_raw_integrity.py) | JSON × Parquet |

## 2. API e fundamentos HTTP

- **Serviço:** GitHub REST API.
- **URL base:** `https://api.github.com`.
- **Método utilizado na extração:** `GET`.
- **Autenticação:** token pessoal enviado no cabeçalho `Authorization: Bearer <TOKEN>`.
- **Formato de resposta:** JSON; listas e objetos com estruturas aninhadas.
- **Consulta parametrizada:** parâmetros na query string, como `per_page`, `page`, `sort`, `since` e `state`, quando aceitos pelo endpoint.

### 2.1 Endpoints estudados

| Endpoint | Finalidade | Observações |
|---|---|---|
| `GET /user` | Validar identidade autenticada | Usado na exploração inicial |
| `GET /user/repos` | Repositórios acessíveis ao usuário autenticado | Pode incluir privados conforme permissões |
| `GET /users/{username}/repos` | Repositórios públicos do usuário | Escopo distinto de `/user/repos` |
| `GET /repos/{owner}/{repo}/commits` | Histórico de commits | Admite `since` e paginação |
| `GET /repos/{owner}/{repo}/issues` | Issues | Pode incluir itens que representam pull requests; verificar campo `pull_request` |
| `GET /repos/{owner}/{repo}/pulls` | Pull requests | A listagem não dispõe do mesmo parâmetro `since` de issues |

**Atenção:** a lista acima documenta os endpoints estudados e o uso pretendido; a rota exata empregada para repositórios deve ser confirmada em `src/ingestion/repositories.py`.

### 2.2 O que é o cabeçalho `Link`?

O GitHub pode devolver, por exemplo:

```http
Link: <https://api.github.com/user/repos?page=2>; rel="next"
```

A presença de `rel="next"` indica uma próxima página. O `GitHubPaginator` acompanha essa referência e reúne os registros até não haver próxima página. Na exploração inicial, foram recuperadas **três páginas com cinco registros cada**.

**Onde mostrar:** `src/api/pagination.py`, `src/api/client.py` (`get_url`) e `notebooks/test_api.py`.

## 3. Erros HTTP e comportamento esperado

| Código ou falha | Significado | Tratamento adotado no projeto | Local para demonstrar |
|---|---|---|---|
| `200` | Sucesso | Retorna a resposta ao fluxo de ingestão | `client.py` / testes de API |
| `400` | Requisição inválida | Exceção específica, sem retry automático | `client.py`, `exceptions.py` |
| `401` | Token ausente/inválido ou falha de autenticação | Exceção de autenticação; não repetir automaticamente | `client.py`, `test_client_recovery.py` |
| `403` comum | Acesso proibido | Exceção sem retry quando não há indícios de rate limit | `client.py`, `test_client_recovery.py` |
| `403` por rate limit | Limitação primária/secundária | Detectar indicadores, calcular espera e tentar novamente dentro dos limites | `client.py` |
| `404` | Recurso não encontrado | Exceção específica, sem retry automático | `client.py`, `exceptions.py` |
| `429` | Requisições excessivas | Espera orientada por cabeçalhos e retry limitado | `client.py` |
| `500`, `502`, `503`, `504` | Erro transitório do serviço/gateway | Retry com backoff exponencial | `client.py`, `test_client_recovery.py` |
| Timeout | Resposta excede o tempo permitido | Retry limitado; exceção ao esgotar tentativas | `client.py`, `test_client_recovery.py` |
| Erro de conexão | Falha de comunicação | Retry limitado; exceção ao esgotar tentativas | `client.py` |
| URL de paginação insegura | URL fora das regras permitidas | Rejeitar antes de enviar a requisição | `client.py`, `test_client_recovery.py` |

**Contexto real de desenvolvimento:** houve retorno **HTTP 401** durante a configuração inicial do token. A autenticação foi corrigida e a consulta a `/user` passou a retornar `200`. Já os cenários de `503`, timeout e rate limit foram **simulados nos testes**; não devem ser descritos como incidentes reais de produção.

## 4. Como a resiliência funciona

### 4.1 Timeout

Um timeout limita o tempo de espera de uma requisição e impede que o processo fique aguardando indefinidamente uma resposta. No cliente, ele é configurável. Quando há timeout, o cliente tenta recuperar a comunicação dentro da política de retries.

**Onde mostrar:** `src/api/client.py` (`GitHubClient`, `_request`) e `notebooks/test_client_recovery.py`.

### 4.2 Retry e backoff exponencial

- **Retry:** nova tentativa após erro considerado temporário.
- **Backoff:** aumento progressivo do intervalo entre tentativas; evita insistência imediata sobre um serviço instável.
- **Limite:** quantidade máxima de tentativas e teto de espera configuráveis.

Exemplo **didático**, não transcrição dos valores efetivos de configuração:

```text
GET -> HTTP 503
espera 1 segundo -> GET -> HTTP 503
espera 2 segundos -> GET -> HTTP 200
requisição recuperada
```

**Onde mostrar:** `src/api/client.py`, `src/utils/exceptions.py` e teste de `HTTP 503` em `notebooks/test_client_recovery.py`.

### 4.3 Rate limit

Os cabeçalhos importantes são:

| Cabeçalho | Uso |
|---|---|
| `X-RateLimit-Limit` | Limite de requisições |
| `X-RateLimit-Remaining` | Requisições ainda disponíveis |
| `X-RateLimit-Used` | Requisições consumidas |
| `X-RateLimit-Reset` | Instante de reinício da janela, em Unix timestamp |
| `Retry-After` | Espera sugerida pelo servidor, quando enviada |

O cliente diferencia `403` de autorização de `403` relacionado à limitação e considera `Retry-After`, `X-RateLimit-Reset` e backoff conforme o cenário. Se a espera exceder o teto configurado, a operação falha de forma controlada.

**Onde mostrar:** `src/api/client.py`; testes de rate limit secundário e limite de espera em `notebooks/test_client_recovery.py`.

### 4.4 Proteção das URLs

A URL completa obtida de um cabeçalho de paginação é validada antes do envio. As regras implementadas incluem HTTPS, host permitido, restrições ao caminho e rejeição de redirecionamentos automáticos. Isso reduz o risco de encaminhar credenciais para um destino inesperado.

**Onde mostrar:** `src/api/client.py` e cenário de URL insegura em `notebooks/test_client_recovery.py`.

### 4.5 Exceções personalizadas

O módulo `src/utils/exceptions.py` organiza as falhas em categorias. Os nomes discutidos durante o desenvolvimento incluem `GitHubAPIError`, `BadRequestError`, `AuthenticationError`, `ResourceNotFoundError`, `RateLimitError`, `ServerError`, `RequestTimeoutError` e `GitHubConnectionError`.

**Verificação necessária:** confirmar a grafia e a hierarquia dessas classes na versão final do arquivo antes de citar nomes em uma apresentação.

## 5. Do JSON à persistência Raw

O GitHub retorna registros JSON, incluindo objetos aninhados como `commit.author`, `owner` e `user`. O projeto usa duas representações:

1. **JSON:** resposta completa, preservada para reprocessamento e auditoria técnica.
2. **Parquet:** campos selecionados, organizados em colunas, com conversão de campos de data quando aplicável.

**Onde mostrar:** `src/storage/raw.py` — `RawStorage.save`, `_save_parquet`, `save_commits_parquet`, `save_repositories_parquet`, `save_issues_parquet`, `save_pull_requests_parquet`.

Particionamento: `data/raw/<entidade>/ingestion_date=YYYY-MM-DD/`.

**Importante:** os nomes dos arquivos JSON e Parquet podem ter timestamps distintos, porque são operações de gravação separadas. A validação de integridade compara identificadores e quantidades dos arquivos selecionados, mas não prova equivalência de todos os campos nem deduplicação histórica global.

## 6. Incrementalidade e checkpoints

### 6.1 Commits, issues e pull requests

O pipeline utiliza referências de execução para identificar registros novos ou alterados e evitar persistência desnecessária. Os commits e issues podem aproveitar filtros temporais da API; para pull requests, a seleção incremental depende da lógica local, pois o endpoint de listagem não oferece o mesmo `since`.

**Onde mostrar:** `src/pipeline/commits.py`, `src/pipeline/resources.py`, `src/utils/checkpoint.py`.

### 6.2 Repositórios: snapshots e eventos

Os repositórios são consultados como snapshot completo e comparados ao estado anterior:

| Evento | Significado |
|---|---|
| `CREATED` | Repositório não registrado no estado anterior |
| `UPDATED` | Metadados monitorados foram modificados |
| `MISSING` | Repositório antes presente não apareceu na consulta atual |
| `RESTORED` | Repositório antes ausente voltou a aparecer |

`MISSING` **não prova exclusão**: a ausência pode decorrer de visibilidade ou permissões. O estado do repositório ausente é preservado para permitir detectar `RESTORED`.

O controle de lotes determinísticos contribui para evitar duplicação de eventos quando uma gravação precisa ser repetida. Isso **não** significa deduplicação de todos os arquivos Raw.

### 6.3 Referências com linhas verificadas em `resources.py`

As linhas abaixo foram identificadas em uma **cópia de `resources.py` fornecida durante o desenvolvimento**. Confira se continuam iguais na branch atual.

| Linhas na versão consultada | Método | Responsabilidade |
|---|---|---|
| 16 | `ResourcesPipeline` | Classe do fluxo de recursos |
| 42–52 | `_load_checkpoint` | Leitura do checkpoint |
| 53–65 | `_save_checkpoint` | Gravação do checkpoint |
| 73–94 | `_filter_incremental` | Seleção de registros incrementais |
| 95–117 | `_update_checkpoint` | Atualização da referência temporal |
| 118–138 | `_persist` | Persistência Raw |
| 143–156 | `_atomic_json_write` | Gravação atômica usada no fluxo de repositórios |
| 157–161 | `_repository_signature` | Assinatura para comparação |
| 162–178 | `_build_repository_state` | Construção do estado atual |
| 179–200 | `_load_previous_repositories_state` | Leitura do estado anterior |
| 201–228 | `_detect_repository_changes` | Detecção de mudanças |
| 229–237 | `_merge_repository_states` | Combinação dos estados |
| 238–245 | `_save_repositories_state` | Persistência do estado |
| 246–251 | `_repository_batch_id` | Identificação determinística do lote |
| 252–277 | `_save_repository_changes` | Persistência dos eventos |
| 278–312 | `run_repositories` | Execução do snapshot e comparação |
| 313–335 | `_run_incremental` | Fluxo incremental genérico |
| 336–341 | `run_issues`, `run_pull_requests` | Entrada dos recursos incrementais |
| 342 em diante | `run` | Orquestração dos recursos |

**Distinção técnica:** a gravação atômica do estado de repositórios não implica que o `CheckpointManager.save()` básico, em `src/utils/checkpoint.py`, seja atômico. Esse último foi apresentado com gravação JSON direta.

## 7. Logging e observabilidade

O pipeline registra início, conclusão, quantidades, duração, erros e tentativas de recuperação. O logger usa saída no terminal e arquivo `logs/github_api.log`, com rotação de tamanho.

**Onde mostrar:** `src/utils/logger.py`, `src/pipeline/main.py`, `src/pipeline/commits.py`, `src/pipeline/resources.py`, `src/api/client.py`.

Um `SUCCESS` no pipeline confirma que a execução terminou sem falha reportada, mas não substitui verificações de integridade, completude ou qualidade de todos os dados históricos.

## 8. Testes e evidências

Executar os comandos **a partir da raiz do projeto**:

```powershell
python -m notebooks.test_api
python -m notebooks.test_parquet
python -m notebooks.test_checkpoint
python -m notebooks.test_incremental
python -m notebooks.test_resources
python -m notebooks.test_resources_pipeline
python -m notebooks.test_repository_changes
python -m notebooks.test_client_recovery
python -m notebooks.test_raw_integrity
python -m src.pipeline.main
```

| Evidência | O que demonstra |
|---|---|
| `test_api.py` | Autenticação, endpoints e paginação |
| `test_client_recovery.py` | Oito cenários simulados de falhas e recuperação |
| `test_checkpoint.py` | Criação, leitura, atualização e isolamento do checkpoint |
| `test_incremental.py` | Comportamento de ingestão incremental |
| `test_repository_changes.py` | Eventos, preservação do estado e idempotência nos casos testados |
| `test_raw_integrity.py` | JSON e Parquet legíveis, identificadores consistentes e timestamps preenchidos |
| `main.py` | Integração dos fluxos e resultado operacional |

### 8.1 Resultado registrado em 11/10/2026

| Entidade | Registros no par selecionado | Colunas Parquet | Resultado |
|---|---:|---:|---|
| Commits | 14 | 7 | PASS |
| Repositories | 47 | 18 | PASS |
| Issues | 2 | 14 | PASS |
| Pull requests | 14 | 15 | PASS |

Os **77 registros** representam os arquivos selecionados pelo teste de integridade, **não** o total histórico coletado.

### 8.2 Evidência de execução integrada

Uma execução integrada reportou `SUCCESS` e processou os quatro recursos. Como os checkpoints já estavam atualizados, não foram identificados novos registros incrementais naquela execução; o snapshot de repositórios foi gerado novamente.

## 9. Como encontrar os números exatos de linha na sua branch

Na raiz do projeto, com a branch atual selecionada, execute no **PowerShell**:

```powershell
# Cliente HTTP: métodos, respostas e controles de resiliência
Select-String -Path 'src/api/client.py' -Pattern 'class GitHubClient','def get','def get_url','def _request','timeout','retry','backoff','rate.limit','Retry-After','X-RateLimit-Reset','allow_redirects' |
    Select-Object Path,LineNumber,Line

# Paginação e autenticação
Select-String -Path 'src/api/pagination.py','src/api/auth.py' -Pattern 'class ','def ','Authorization','Link','next' |
    Select-Object Path,LineNumber,Line

# Persistência e checkpoints
Select-String -Path 'src/storage/raw.py','src/utils/checkpoint.py' -Pattern 'class ','def ','to_parquet','json.dump','ingestion_date' |
    Select-Object Path,LineNumber,Line

# Eventos e incrementalidade
Select-String -Path 'src/pipeline/resources.py' -Pattern 'def _filter_incremental','def _detect_repository_changes','def _repository_batch_id','def _save_repository_changes','def run_repositories' |
    Select-Object Path,LineNumber,Line

# Testes de falha e recuperação
Select-String -Path 'notebooks/test_client_recovery.py' -Pattern 'def ','401','403','503','timeout','rate','unsafe' |
    Select-Object Path,LineNumber,Line
```

Para obter **links permanentes com linha**, abra o arquivo no GitHub, selecione a linha e copie o link. Preferencialmente, utilize um link para o **SHA do commit**, não para uma branch mutável. Exemplo de formato (substitua os campos):

```text
https://github.com/milenoepifanio/github-api-data-pipeline/blob/<SHA_DO_COMMIT>/src/api/client.py#L<INICIO>-L<FIM>
```

### 9.1 Registro das linhas finais — preencher após revisão

| Evidência | Link com linha do commit final |
|---|---|
| Autenticação e token | PENDENTE |
| Construção de requisições e parâmetros | PENDENTE |
| Paginação pelo Link | PENDENTE |
| Timeout | PENDENTE |
| Retry e backoff | PENDENTE |
| Rate limit e cabeçalhos | PENDENTE |
| Exceções HTTP | PENDENTE |
| Validação de URL | PENDENTE |
| Gravação JSON | PENDENTE |
| Gravação Parquet | PENDENTE |
| Checkpoints | PENDENTE |
| Eventos CREATED/UPDATED/MISSING/RESTORED | PENDENTE |
| Idempotência de lotes | PENDENTE |
| Logging | PENDENTE |
| Testes de recuperação | PENDENTE |

## 10. Limitações e cuidados de interpretação

1. **Raw não é Silver:** os dados estruturados em Parquet ainda fazem parte da camada Raw do projeto.
2. **Sem deduplicação histórica global:** retroceder checkpoints pode gerar novos lotes com registros já persistidos.
3. **Snapshot não é evento:** o snapshot de repositórios é completo; os eventos representam diferenças entre estados.
4. **MISSING não é exclusão confirmada:** indica ausência na consulta atual.
5. **Testes simulados não são incidentes reais:** diferenciar erros reproduzidos em teste de falhas observadas durante o desenvolvimento.
6. **Logs não garantem qualidade:** são evidências de execução, complementadas por validações dos dados.
7. **Linhas de código mudam:** fixar links a commits para documentação auditável.

## 11. Relação com o PDI

| Tarefa do PDI | Capítulos e arquivos principais |
|---|---|
| 1. Fundamentos e exploração | Seções 2 e 3; `docs/api_exploration.md`; `test_api.py` |
| 2. Ingestão com Python | Seções 1 e 2; `auth.py`, `client.py`, `pagination.py`, `src/ingestion/` |
| 3. Resiliência | Seções 3 e 4; `client.py`, `exceptions.py`, `test_client_recovery.py` |
| 4. Raw e incrementalidade | Seções 5 e 6; `raw.py`, `checkpoint.py`, `resources.py` |
| 5. Testes, logs e documentação | Seções 7–9; `logger.py`, `notebooks/`, `docs/` |

## 12. Leituras complementares

- [README do projeto](../README.md)
- [Arquitetura](architecture.md)
- [Exploração da API](api_exploration.md)
- [Cliente HTTP](client.md)
- [Estratégia incremental](incremental_strategy.md)
- [Evidências do PDI](pdi-evidence.md) — quando o arquivo estiver versionado
- [Documentação oficial da API REST do GitHub](https://docs.github.com/en/rest)
- [Paginação](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
- [Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
