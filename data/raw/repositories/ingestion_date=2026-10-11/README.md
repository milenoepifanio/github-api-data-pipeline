# Repositórios — Ingestão de 11/10/2026

Esta pasta reúne os snapshots de repositórios gerados pela ingestão realizada em 11 de outubro de 2026.

## Finalidade

Os arquivos registram os resultados de diferentes execuções da consulta de repositórios do usuário:

- JSON com as respostas brutas recebidas da API;
- Parquet com os metadados estruturados dos repositórios.

---

## Estrutura

| Conteúdo | Descrição |
| --- | --- |
| Arquivos `.json` | Snapshots brutos dos repositórios por execução |
| Arquivos `.parquet` | Metadados tabulares correspondentes aos snapshots |
| `.gitkeep` | Marcador para preservar a pasta no repositório sem os dados gerados |

---

## Observações

Os arquivos JSON e Parquet são artefatos gerados e ignorados pelo Git. A comparação entre snapshots é usada pelo pipeline para identificar alterações nos repositórios.
