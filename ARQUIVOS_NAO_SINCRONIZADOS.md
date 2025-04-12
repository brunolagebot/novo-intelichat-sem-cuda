# Arquivos Não Sincronizados

Este documento lista todos os arquivos que não são sincronizados com o GitHub e fornece instruções sobre como obtê-los ou criá-los para executar o projeto corretamente.

## 1. Arquivos de Ambiente

### `.env`
Arquivo de configuração com variáveis de ambiente.

```env
OLLAMA_DEFAULT_MODEL=llama3
OLLAMA_API_HOST=http://localhost:11434
DB_PATH=chat_history.db
```

**Como criar**: 
1. Copie o exemplo acima para um novo arquivo chamado `.env` na raiz do projeto
2. Ajuste os valores conforme sua necessidade

## 2. Arquivos de Modelo

### Diretório: `results-llama3-8b-chat-adapter/`
Contém os arquivos do modelo adaptado para chat.

**Como obter**:
1. Baixe o modelo base do Ollama:
```bash
ollama pull llama2
```

2. Execute o script de fine-tuning (requer GPU):
```bash
python scripts/run_finetune.py
```

Alternativamente, você pode usar o modelo base sem fine-tuning:
1. Modifique o arquivo `.env`
2. Defina `OLLAMA_DEFAULT_MODEL=llama2`

### Diretório: `results-llama3-8b-chat-schema-adapter/`
Contém os arquivos do modelo adaptado para processamento de schemas.

**Como obter**:
1. Baixe o modelo base do Ollama (se ainda não tiver):
```bash
ollama pull llama2
```

2. Execute o script de fine-tuning específico para schemas (requer GPU):
```bash
python scripts/run_finetune_schema.py
```

## 3. Banco de Dados

### `chat_history.db`
Banco de dados SQLite que armazena o histórico de conversas.

**Como criar**:
1. O banco será criado automaticamente na primeira execução
2. Alternativamente, execute:
```bash
python check_db.py
```

## 4. Arquivos de Cache

### `response_cache.json`
Cache local de respostas do modelo para melhorar performance.

**Como criar**:
- Será criado automaticamente durante a execução
- Não requer configuração manual

## Observações Importantes

1. **Modelos Alternativos**: Se você não tem GPU disponível, recomendamos:
   - Usar modelos menores do Ollama (como `llama2:7b`)
   - Ajustar o `.env` para usar o modelo base sem fine-tuning

2. **Armazenamento Necessário**:
   - Modelos completos: ~8GB por modelo
   - Banco de dados: cresce conforme o uso (~100MB inicial)
   - Cache: tamanho variável (~10MB inicial)

3. **Requisitos de Sistema**:
   - RAM: Mínimo 16GB recomendado
   - Armazenamento: 20GB livres para todos os arquivos
   - GPU: Opcional (apenas para fine-tuning) 