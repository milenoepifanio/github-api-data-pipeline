
# GitHub API Data Pipeline

## Sobre o projeto

O **GitHub API Data Pipeline** é um projeto de Engenharia de Dados desenvolvido em Python para realizar a ingestão de informações disponibilizadas pela API REST do GitHub.

O projeto implementa um pipeline de dados com autenticação, paginação, tratamento de erros, controle de requisições, persistência de dados e processamento incremental.

A solução foi desenvolvida como parte de um Plano de Desenvolvimento Individual (PDI), com foco no aprimoramento de competências relacionadas à integração com APIs Web e à construção de pipelines de dados.

O objetivo é demonstrar, na prática, como construir um processo de ingestão confiável, organizado, rastreável e preparado para evoluções futuras.

---

## 1. Objetivos

O projeto possui os seguintes objetivos:

- Consumir dados da API REST do GitHub.
- Implementar autenticação por token.
- Trabalhar com endpoints parametrizados.
- Realizar paginação de resultados.
- Tratar falhas de conexão e timeout.
- Implementar tentativas automáticas de recuperação.
- Respeitar os limites de requisições da API.
- Persistir respostas completas em JSON.
- Armazenar dados estruturados em Parquet.
- Implementar ingestão incremental.
- Controlar o processamento por checkpoints.
- Identificar alterações no estado dos repositórios.
- Registrar logs operacionais.
- Validar a integridade dos dados persistidos.

---

## 2. Tecnologias utilizadas

| Tecnologia | Finalidade |
|---|---|
| Python | Desenvolvimento do pipeline |
| GitHub REST API | Fonte dos dados |
| Requests | Comunicação HTTP |
| Pandas | Estruturação e manipulação dos dados |
| PyArrow | Persistência em Parquet |
| JSON | Armazenamento das respostas completas |
| YAML | Configuração do projeto |
| Logging | Monitoramento e rastreabilidade |
| Git e GitHub | Versionamento do código |

---

## 3. Recursos disponíveis

O pipeline realiza a ingestão de quatro recursos da API REST do GitHub.

| Recurso | Descrição |
|---|---|
| Repositories | Metadados dos repositórios de um usuário |
| Commits | Histórico de commits de um repositório |
| Issues | Issues associadas a um repositório |
| Pull Requests | Solicitações de alteração de código |

Cada recurso possui uma estratégia de ingestão adequada às características dos dados.

### 3.1 Repositories

Os repositórios são consultados integralmente a cada execução.

O pipeline persiste um snapshot dos registros e compara o estado atual com o checkpoint anterior.

Essa comparação permite identificar os seguintes eventos:

- `CREATED`: repositório identificado pela primeira vez.
- `UPDATED`: alteração nos metadados monitorados.
- `MISSING`: repositório anteriormente conhecido que não aparece na consulta atual.
- `RESTORED`: repositório anteriormente ausente que voltou a aparecer.

Os eventos são armazenados separadamente dos snapshots.

### 3.2 Commits

A ingestão de commits utiliza checkpoints para identificar registros que precisam ser processados.

O pipeline consulta a API considerando a referência temporal armazenada e aplica as regras de identificação dos novos registros.

### 3.3 Issues

A ingestão de issues utiliza a estratégia incremental baseada nas informações de atualização disponibilizadas pela API.

### 3.4 Pull Requests

A ingestão de pull requests também utiliza checkpoints e identificação incremental de registros.

---

## 4. Arquitetura

O pipeline segue uma arquitetura modular, separando responsabilidades de comunicação com a API, ingestão, orquestração, persistência e controle operacional.

```text
GitHub REST API
       |
       v
Autenticação
       |
       v
Cliente HTTP
       |
       +---- Timeout
       +---- Retry
       +---- Backoff
       +---- Rate Limit
       |
       v
Paginação
       |
       v
Módulos de Ingestão
       |
       +---- Commits
       +---- Repositories
       +---- Issues
       +---- Pull Requests
       |
       v
Orquestração do Pipeline
       |
       +---- Controle Incremental
       +---- Checkpoints
       +---- Detecção de Alterações
       +---- Logging
       |
       v
Camada Raw
       |
       +---- JSON
       +---- Parquet
```

A solução implementa a camada **Raw**, responsável por preservar os dados recebidos da API e disponibilizar representações estruturadas para processamento posterior.

Uma camada Silver não faz parte do escopo atual.

Para mais detalhes, consulte [Arquitetura](docs/architecture.md).

---

## 5. Estrutura do projeto

```text
github-api-data-pipeline/
|
|-- config/
|   |-- config.yaml
|
|-- data/
|   |-- raw/
|   |   |-- commits/
|   |   |-- repositories/
|   |   |-- issues/
|   |   |-- pull_requests/
|   |
|   |-- checkpoints/
|   |
|   |-- changes/
|       |-- repositories/
|           |-- batches/
|
|-- docs/
|   |-- architecture.md
|   |-- api_exploration.md
|   |-- client.md
|   |-- incremental_strategy.md
|
|-- logs/
|   |-- github_api.log
|
|-- notebooks/
|   |-- test_api.py
|   |-- test_parquet.py
|   |-- test_checkpoint.py
|   |-- test_incremental.py
|   |-- test_resources.py
|   |-- test_resources_pipeline.py
|   |-- test_repository_changes.py
|   |-- test_client_recovery.py
|   |-- test_raw_integrity.py
|
|-- src/
|   |-- api/
|   |   |-- auth.py
|   |   |-- client.py
|   |   |-- pagination.py
|   |
|   |-- ingestion/
|   |   |-- commits.py
|   |   |-- repositories.py
|   |   |-- issues.py
|   |   |-- pull_requests.py
|   |
|   |-- pipeline/
|   |   |-- commits.py
|   |   |-- resources.py
|   |   |-- main.py
|   |
|   |-- storage/
|   |   |-- raw.py
|   |
|   |-- utils/
|       |-- checkpoint.py
|       |-- exceptions.py
|       |-- logger.py
|
|-- .env.example
|-- .gitignore
|-- requirements.txt
|-- README.md
```

---

## 6. Instalação

### 6.1 Pré-requisitos

- Python instalado.
- Git instalado.
- Conta no GitHub.
- Token de acesso pessoal do GitHub.
- Acesso à internet.

### 6.2 Clonar o repositório

```bash
git clone https://github.com/milenoepifanio/github-api-data-pipeline.git

cd github-api-data-pipeline
```

### 6.3 Criar um ambiente virtual

No Windows:

```powershell
python -m venv .venv

.\.venv\Scripts\Activate.ps1
```

### 6.4 Instalar dependências

```powershell
pip install -r requirements.txt
```

### 6.5 Configurar autenticação

Crie um arquivo `.env` com base no `.env.example`.

Configure o token de acesso pessoal do GitHub utilizando o nome de variável esperado pelo módulo `src/api/auth.py`.

O token deve possuir as permissões necessárias para acessar os recursos utilizados.

**Nunca publique o arquivo `.env` ou o token no repositório.**

---

## 7. Execução do pipeline

A execução principal é realizada a partir da raiz do projeto:

```powershell
python -m src.pipeline.main
```

O pipeline executa dois fluxos principais:

1. Ingestão incremental de commits.
2. Ingestão de repositories, issues e pull requests.

Ao final, são registrados logs com o resultado de cada etapa.

Exemplo:

```text
GitHub API Data Pipeline started
[1/2] Starting Commits Pipeline
Commits ingestion completed | Status=SUCCESS
[2/2] Starting Resources Pipeline
GitHub Resources Pipeline completed | Status=SUCCESS
GitHub API Data Pipeline completed | Status=SUCCESS
```

---

## 8. Persistência dos dados

Os dados são armazenados localmente na camada Raw.

### 8.1 JSON

Os arquivos JSON preservam os registros completos recebidos da API.

### 8.2 Parquet

Os arquivos Parquet armazenam os campos selecionados e estruturados para análise e processamento.

### 8.3 Particionamento

A organização utiliza a data de ingestão:

```text
data/raw/
    commits/
        ingestion_date=YYYY-MM-DD/
            arquivo.json
            arquivo.parquet
```

A mesma organização é utilizada para repositories, issues e pull requests.

Os nomes dos arquivos incluem timestamps para identificar os lotes gerados.

---

## 9. Processamento incremental

O pipeline utiliza checkpoints para armazenar referências do último processamento bem-sucedido.

Os checkpoints são mantidos em:

```text
data/checkpoints/
```

Exemplos:

```text
commits.json
repositories_milenoepifanio.json
issues_milenoepifanio_github-api-data-pipeline.json
pull_requests_milenoepifanio_github-api-data-pipeline.json
```

A estratégia reduz o reprocessamento desnecessário de dados incrementais.

A ingestão de repositórios utiliza snapshots completos e comparação de estados, em vez de depender exclusivamente de um filtro temporal.

Mais detalhes estão disponíveis em [Estratégia Incremental](docs/incremental_strategy.md).

---

## 10. Tratamento de erros

O cliente HTTP possui mecanismos de recuperação para falhas transitórias.

Entre os cenários tratados estão:

- Timeout.
- Falhas de conexão.
- Respostas HTTP 500, 502, 503 e 504.
- Limites primários e secundários de requisições.
- Respostas HTTP não recuperáveis.

O mecanismo utiliza tentativas automáticas com espera progressiva, respeitando o limite máximo configurado.

Erros de autenticação e outros problemas não transitórios são tratados sem tentativas desnecessárias.

Consulte [Cliente HTTP](docs/client.md).

---

## 11. Logging e observabilidade

O pipeline registra informações sobre:

- Início e término das execuções.
- Recursos processados.
- Quantidade de registros consultados.
- Quantidade de registros persistidos.
- Carregamento e atualização de checkpoints.
- Alterações detectadas em repositórios.
- Tentativas de recuperação.
- Falhas e exceções.
- Tempo de execução.

Os logs são disponibilizados no terminal e em:

```text
logs/github_api.log
```

O arquivo utiliza rotação para limitar o crescimento dos logs.

---

## 12. Testes

O projeto utiliza scripts de validação funcional, executados diretamente pelo Python.

### 12.1 Testes disponíveis

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
```

Alguns testes consultam a API real e podem criar novos arquivos Raw. Outros utilizam dados simulados e diretórios temporários.

### 12.2 Validação de integridade

O teste `test_raw_integrity.py` verifica:

- Leitura de JSON.
- Leitura de Parquet.
- Presença das colunas obrigatórias.
- Identificadores não nulos.
- Unicidade dos identificadores dentro dos arquivos selecionados.
- Consistência de quantidade e identificadores entre JSON e Parquet.
- Preenchimento dos timestamps de ingestão.

Na validação realizada em 11/10/2026, foram aprovadas as quatro entidades:

| Entidade | Registros | Resultado |
|---|---:|---|
| Commits | 14 | PASS |
| Repositories | 47 | PASS |
| Issues | 2 | PASS |
| Pull Requests | 14 | PASS |

Os testes verificam arquivos selecionados e cenários específicos. Não representam uma auditoria completa de todos os arquivos históricos.

---

## 13. Limitações conhecidas

A implementação atual possui algumas limitações:

- Persistência local, sem armazenamento em nuvem.
- Ausência de uma camada Silver.
- Ausência de orquestração externa por agendador.
- Ausência de deduplicação global entre todos os lotes Raw.
- Checkpoints de commits gravados diretamente no arquivo definitivo.
- Testes funcionais executados manualmente, sem integração obrigatória a uma esteira de CI/CD.

O retrocesso manual de checkpoints pode provocar a persistência de registros já existentes em lotes anteriores.

Esses pontos representam oportunidades de evolução do projeto.

---

## 14. Documentação complementar

- [Arquitetura](docs/architecture.md)
- [Exploração da API](docs/api_exploration.md)
- [Cliente HTTP](docs/client.md)
- [Estratégia Incremental](docs/incremental_strategy.md)

---

## 15. Evoluções futuras

Possíveis melhorias:

- Implementar persistência atômica de checkpoints.
- Criar uma camada Silver para tratamento e padronização.
- Implementar deduplicação histórica entre lotes.
- Integrar armazenamento em nuvem.
- Adicionar execução automatizada e agendamento.
- Integrar os testes a uma pipeline de CI/CD.
- Implementar métricas operacionais e alertas.

---

## 16. Autor

**Mileno Epifanio**

Projeto desenvolvido para aprimoramento técnico em Engenharia de Dados, com foco em integração com APIs Web, persistência, incrementalidade, observabilidade e confiabilidade de pipelines.
