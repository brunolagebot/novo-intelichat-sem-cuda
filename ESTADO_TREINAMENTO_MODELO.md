# Estado do Treinamento do Modelo - Esquema Firebird

Este documento descreve o processo atual para gerar dados de treinamento focados no esquema e significado do banco de dados Firebird (`DADOS.FDB`), e como esses dados se integram a outros esforços de treinamento.

## Objetivo

O objetivo principal desta fase é ensinar ao modelo de linguagem (atualmente Llama 3 8B, acessado via Ollama) sobre:

1.  A **estrutura técnica** do banco de dados Firebird: tabelas, views, colunas, tipos de dados, chaves primárias e estrangeiras.
2.  O **significado semântico e de negócio** dessas estruturas: o que cada tabela representa, o propósito de cada coluna, e o significado de valores específicos (mapeamentos).

## Processo Atual

O processo está dividido em duas etapas principais:

1.  **Extração do Esquema Técnico:**
    *   **Ferramenta:** Script `extract_firebird_schema.py`.
    *   **Entrada:** Conexão direta ao banco `DADOS.FDB`.
    *   **Saída:** Arquivo `firebird_schema.json`, contendo a estrutura técnica (nomes, tipos, constraints, tipo de objeto - TABLE/VIEW).

2.  **Anotação Interativa de Metadados:**
    *   **Ferramenta:** Aplicação web Streamlit `view_schema_app.py`.
    *   **Entrada:**
        *   `firebird_schema.json` (para exibir a estrutura).
        *   Interação do usuário (você!) para adicionar/editar descrições e mapeamentos de valores.
        *   (Opcional) Sugestões de descrição geradas pela IA (Ollama) através dos botões "Sugerir (IA)".
    *   **Saída:** Arquivo `schema_metadata.json`, contendo as descrições de tabelas/views, descrições de colunas e notas sobre mapeamentos de valores inseridos pelo usuário.
    *   **Status Atual:** Estamos nesta fase, usando a aplicação Streamlit para criar/refinar o `schema_metadata.json`.

## Próxima Etapa: Geração dos Dados de Treinamento

Após a conclusão da anotação e a finalização do `schema_metadata.json`:

1.  **Criaremos um script** (ex: `generate_schema_training_data.py`).
2.  Este script **lerá** ambos os arquivos:
    *   `firebird_schema.json` (estrutura)
    *   `schema_metadata.json` (significado/contexto)
3.  Ele **gerará exemplos de treinamento** no formato Pergunta/Resposta (User/Assistant). Estes exemplos cobrirão:
    *   Perguntas sobre a estrutura (Ex: "Liste colunas da tabela X").
    *   Perguntas sobre o significado (Ex: "O que significa a coluna Y?", "O que representa o valor Z na coluna Y?").
    *   (Opcional) Geração de SQL simples relacionado ao esquema.
4.  A **saída** será um arquivo no formato **JSON Lines (`.jsonl`)**, por exemplo `firebird_schema_training_data.jsonl`.
5.  Cada linha neste arquivo `.jsonl` conterá um único exemplo de treinamento, estruturado como um objeto JSON com a chave `"messages"` contendo uma lista de dicionários com `"role"` (user/assistant) e `"content"`, exatamente como especificado no documento `COMO_TREINAR_O_MODELO.md`.

## Reaproveitamento e Concatenação

Este processo foi desenhado para ser modular e permitir a combinação com outros treinamentos, como o que você está realizando em outro computador:

1.  **Formato Padronizado (`.jsonl`):** A chave para a combinação é o formato de saída. O arquivo `firebird_schema_training_data.jsonl` (e qualquer outro arquivo de treinamento gerado seguindo as diretrizes de `COMO_TREINAR_O_MODELO.md`) terá a mesma estrutura base (linhas de JSON com `{"messages": [...]}`).
2.  **Concatenação de Datasets:** Para treinar o modelo com múltiplos conhecimentos (ex: esquema Firebird + outra tarefa), você pode simplesmente **concatenar** os arquivos `.jsonl` correspondentes. Por exemplo, combinar `firebird_schema_training_data.jsonl` e `outra_tarefa_data.jsonl` em um único arquivo `combined_training_data.jsonl`.
3.  **Adaptadores LoRA Modulares:** Como descrito em `COMO_TREINAR_O_MODELO.md`, a abordagem recomendada é usar cada dataset `.jsonl` focado para treinar um **adaptador LoRA separado** a partir do **modelo base original**. Você teria:
    *   Um adaptador treinado com `firebird_schema_training_data.jsonl` (ex: `firebird-schema-adapter`).
    *   Outro adaptador treinado com os dados do seu outro processo (ex: `outra-tarefa-adapter`).
4.  **Combinação na Inferência:** Ao usar o modelo para responder perguntas, você **carrega o modelo base e múltiplos adaptadores LoRA simultaneamente**. Por exemplo, carregar o `schema-adapter` e o `outra-tarefa-adapter`. O modelo então terá acesso ao conhecimento especializado de ambos os adaptadores.

## Resumo

Estamos atualmente criando um conjunto rico de metadados (`schema_metadata.json`) que descreve o significado do nosso esquema Firebird (`firebird_schema.json`), usando uma ferramenta Streamlit interativa com auxílio opcional de IA. Estes metadados serão usados para gerar um arquivo de treinamento focado (`.jsonl`) no formato correto. Graças ao formato padronizado e à abordagem de adaptadores LoRA, este treinamento será modular e poderá ser facilmente combinado com outros treinamentos específicos durante a fase de inferência. 