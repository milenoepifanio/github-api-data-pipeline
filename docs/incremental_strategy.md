
# Estratégia de Ingestão Incremental

## Sobre

Este documento descreve a estratégia de ingestão incremental utilizada pelo GitHub API Data Pipeline.

O objetivo é reduzir o reprocessamento desnecessário, manter referências de execução e permitir a identificação de novos registros e alterações nos dados consultados.

A estratégia utiliza:

- Checkpoints.
- Referências temporais.
- Identificação de registros incrementais.
- Snapshots.
- Comparação de estados.
- Eventos de alteração.
- Controle de idempotência.

---

# 1. Conceito de ingestão incremental

A ingestão incremental consiste em processar os dados novos ou modificados desde uma referência anterior.

Em vez de persistir novamente todo o histórico a cada execução, o pipeline utiliza informações de controle para identificar o que precisa ser processado.

Exemplo:

```text
Execução 1
    |
    +---- Registro A
    +---- Registro B
    +---- Registro C
    |
    v
Checkpoint atualizado

Execução 2
    |
    +---- Registro D
    +---- Registro E
    |
    v
Novo checkpoint
```

A aplicação dessa estratégia depende das características de cada endpoint.

---

# 2. Checkpoints

Os checkpoints armazenam referências utilizadas para controlar o processamento.

O projeto implementa o gerenciamento básico em:

```text
src/utils/checkpoint.py
```

A classe `CheckpointManager` disponibiliza:

- `load()`: leitura do checkpoint.
- `save()`: gravação do checkpoint.

## 2.1 Estrutura

Exemplo:

```json
{
  "entity": "commits",
  "last_processed_at": "2026-10-11T13:44:59Z"
}
```

## 2.2 Armazenamento

Os arquivos são mantidos em:

```text
data/checkpoints/
```

Cada entidade utiliza sua própria referência de controle.

## 2.3 Primeira execução

Quando um checkpoint não existe, o gerenciador retorna `None`.

O pipeline deve então aplicar a estratégia inicial definida para o recurso.

## 2.4 Execuções seguintes

Nas execuções posteriores, o checkpoint é utilizado para determinar a referência do processamento incremental.

Após a conclusão bem-sucedida das etapas necessárias, o checkpoint é atualizado.

---

# 3. Estratégia para commits

Os commits possuem identificadores SHA e informações temporais.

O pipeline utiliza uma referência temporal para consultar os registros relevantes.

Fluxo:

```text
Carregar checkpoint
        |
        v
Definir referência temporal
        |
        v
Consultar commits
        |
        v
Identificar registros incrementais
        |
        +---- Nenhum registro novo
        |          |
        |          v
        |       Encerrar
        |
        v
Persistir JSON
        |
        v
Persistir Parquet
        |
        v
Atualizar checkpoint
```

A identificação dos registros incrementais considera as regras implementadas no pipeline, incluindo a referência temporal e o controle dos registros consultados.

O objetivo é evitar persistências desnecessárias durante execuções normais.

---

# 4. Estratégia para issues

Issues possuem identificadores próprios e informações de criação e atualização.

A API disponibiliza um parâmetro `since` para consultar registros atualizados após uma referência temporal.

O pipeline utiliza checkpoints para identificar os registros que precisam ser processados.

Fluxo:

1. Carregar checkpoint.
2. Consultar issues.
3. Identificar registros incrementais.
4. Persistir JSON e Parquet quando necessário.
5. Atualizar o checkpoint após o processamento bem-sucedido.

O processamento incremental pode envolver registros atualizados, não apenas registros criados pela primeira vez.

---

# 5. Estratégia para pull requests

Pull requests possuem informações temporais e identificadores próprios.

O endpoint de listagem de pull requests não disponibiliza o mesmo filtro `since` utilizado em outros recursos.

Por isso, a estratégia incremental depende da consulta dos registros e da aplicação das regras de identificação no pipeline.

Fluxo:

1. Carregar checkpoint.
2. Consultar pull requests.
3. Avaliar os registros retornados.
4. Identificar registros incrementais.
5. Persistir os registros necessários.
6. Atualizar o checkpoint após o processamento.

---

# 6. Estratégia para repositories

A ingestão de repositórios utiliza uma abordagem diferente.

Em vez de depender exclusivamente de uma referência temporal, o pipeline recupera um snapshot completo e compara seu conteúdo com o estado anterior.

Essa abordagem permite identificar alterações nos metadados monitorados.

## 6.1 Fluxo

```text
Consultar repositórios
        |
        v
Persistir snapshot Raw
        |
        v
Carregar estado anterior
        |
        v
Comparar estados
        |
        v
Detectar eventos
        |
        +---- CREATED
        +---- UPDATED
        +---- MISSING
        +---- RESTORED
        |
        v
Persistir eventos
        |
        v
Atualizar estado
```

---

# 7. Eventos de alteração

## 7.1 CREATED

Ocorre quando um repositório aparece no estado atual e não estava registrado anteriormente.

## 7.2 UPDATED

Ocorre quando um repositório já conhecido apresenta alterações nos metadados monitorados.

## 7.3 MISSING

Ocorre quando um repositório anteriormente conhecido deixa de aparecer na consulta atual.

Isso não comprova que o repositório foi excluído definitivamente.

Ele pode ter sido removido, tornado inacessível ou deixado de aparecer por outro motivo.

## 7.4 RESTORED

Ocorre quando um repositório anteriormente marcado como ausente volta a aparecer.

O estado anterior é preservado para permitir essa identificação.

---

# 8. Persistência dos eventos

Os eventos são armazenados em:

```text
data/changes/repositories/batches/
```

A implementação utiliza identificadores determinísticos para os lotes.

Esse mecanismo permite reconhecer um lote já persistido durante uma nova tentativa.

Exemplo:

```text
Primeira tentativa
        |
        v
Evento identificado
        |
        v
Lote persistido
        |
        v
Falha posterior

Nova tentativa
        |
        v
Mesmo evento identificado
        |
        v
Lote já existe
        |
        v
Evitar duplicação do lote
```

A estratégia contribui para a idempotência do processamento de eventos.

---

# 9. Idempotência

Uma operação idempotente pode ser executada novamente sem produzir efeitos adicionais indesejados.

No projeto, esse conceito é aplicado especialmente à persistência dos eventos de alteração dos repositórios.

Os testes validaram:

- Reconhecimento de lotes existentes.
- Reexecução de eventos.
- Ausência de duplicação dos lotes testados.
- Preservação do estado após falhas simuladas.

A idempotência dos eventos não significa que todos os arquivos Raw sejam globalmente deduplicados.

---

# 10. Recuperação de falhas

A atualização dos checkpoints deve ocorrer somente após a conclusão das etapas necessárias.

Nos testes de repositórios, foram simuladas falhas em:

- Persistência do snapshot.
- Persistência dos eventos.
- Gravação do checkpoint.

Os cenários foram validados para confirmar que o estado anterior não avançasse indevidamente.

Essa proteção permite repetir operações após determinadas falhas.

Entretanto, arquivos já persistidos antes de uma interrupção podem permanecer no armazenamento.

---

# 11. Retrocesso manual de checkpoints

Uma limitação importante foi identificada durante os testes.

Ao modificar manualmente um checkpoint de commits para uma data anterior, o pipeline pode recuperar e persistir novamente registros já armazenados em lotes anteriores.

Exemplo:

```text
Checkpoint atual
2026-10-11
        |
        v
Retrocesso manual
2026-10-05
        |
        v
Nova execução
        |
        v
Commits antigos recuperados novamente
        |
        v
Novo lote Raw
```

Esse comportamento não representa necessariamente uma falha no processamento incremental normal.

Ele evidencia a ausência de deduplicação histórica global entre os arquivos Raw.

Portanto, checkpoints reais não devem ser alterados por scripts de teste.

---

# 12. Testes de checkpoint

O arquivo:

```text
notebooks/test_checkpoint.py
```

utiliza diretórios temporários para validar o gerenciamento dos checkpoints sem modificar os arquivos reais.

Os cenários incluem:

1. Estado inicial sem checkpoint.
2. Criação do checkpoint.
3. Leitura do valor persistido.
4. Atualização do checkpoint.
5. Validação da estrutura JSON.
6. Recuperação por uma nova instância.
7. Limpeza do diretório temporário.

A utilização de diretórios isolados evita efeitos colaterais sobre as execuções do pipeline.

---

# 13. Testes de incrementalidade

O projeto também disponibiliza:

```text
notebooks/test_incremental.py
notebooks/test_resources_pipeline.py
notebooks/test_repository_changes.py
```

Esses scripts verificam cenários relacionados a:

- Consulta incremental.
- Persistência de registros.
- Execuções repetidas.
- Detecção de alterações.
- Reprocessamento de eventos.
- Recuperação de falhas simuladas.

A validação integrada confirmou execuções sem novos registros incrementais quando não havia alterações identificadas.

---

# 14. Limitações conhecidas

A implementação atual não oferece:

- Deduplicação histórica global entre lotes Raw.
- Controle transacional entre todos os arquivos.
- Armazenamento distribuído de checkpoints.
- Controle de concorrência entre múltiplas execuções simultâneas.
- Persistência atômica no gerenciador básico de checkpoints.
- Reprocessamento histórico com controle global de versões.

Essas limitações devem ser consideradas antes de adaptar o projeto para ambientes com maior volume de dados ou múltiplos processos concorrentes.

---

# 15. Evoluções futuras

Possíveis melhorias:

## 15.1 Persistência atômica de checkpoints

Gravar primeiro em um arquivo temporário e substituir o arquivo definitivo somente após a conclusão da escrita.

## 15.2 Deduplicação histórica

Implementar controle de identificadores já processados entre diferentes lotes Raw.

## 15.3 Controle de versões

Registrar informações adicionais sobre as execuções e os estados processados.

## 15.4 Armazenamento externo

Migrar checkpoints para uma solução persistente compartilhada, conforme a necessidade arquitetural.

## 15.5 Camada Silver

Implementar tratamentos e consolidações para produzir conjuntos de dados estruturados e deduplicados.

---

# 16. Documentos relacionados

- [README](../README.md)
- [Arquitetura](architecture.md)
- [Exploração da API](api_exploration.md)
- [Cliente HTTP](client.md)
