import json
import os
import logging
from tqdm import tqdm
from src.ollama_integration.client import chat_completion # Usamos nosso cliente existente

# --- Configuração ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

SCHEMA_FILE = "firebird_schema.json"
OUTPUT_DRAFT_FILE = "schema_metadata_draft.json"

# --- Funções Auxiliares ---

def load_schema(file_path):
    """Carrega o esquema técnico do banco de dados do arquivo JSON."""
    if not os.path.exists(file_path):
        logger.error(f"Erro: Arquivo de esquema '{file_path}' não encontrado.")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Erro: Arquivo de esquema '{file_path}' não é um JSON válido.")
        return None
    except Exception as e:
        logger.exception(f"Erro inesperado ao carregar o esquema '{file_path}':")
        return None

def generate_ai_description(prompt):
    """Chama a API Ollama para gerar uma descrição e limpa a resposta."""
    logger.debug(f"Enviando prompt para IA: {prompt}")
    # Usamos a função chat_completion que já lida com o modelo padrão do .env
    # Construímos a lista de mensagens como esperado pela função
    messages = [{"role": "user", "content": prompt}]
    response = chat_completion(messages=messages, stream=False)

    if response:
        # Limpeza básica: remover aspas extras, espaços em branco
        cleaned_response = response.strip().strip('"').strip('\'').strip()
        logger.debug(f"Resposta da IA (limpa): {cleaned_response}")
        return cleaned_response
    else:
        logger.warning("Falha ao obter descrição da IA.")
        return "[Descrição não gerada pela IA]"

def main():
    logger.info(f"Iniciando geração de rascunho de metadados a partir de {SCHEMA_FILE}")
    schema_data = load_schema(SCHEMA_FILE)
    if not schema_data:
        return

    draft_metadata = {"TABLES": {}, "VIEWS": {}}

    # Usar tqdm para barra de progresso sobre os objetos (tabelas/views)
    total_objects = len(schema_data)
    logger.info(f"Encontrados {total_objects} objetos (tabelas/views) no esquema.")
    object_iterator = tqdm(schema_data.items(), total=total_objects, desc="Gerando descrições para tabelas/views")

    for object_name, object_info in object_iterator:
        object_type = object_info.get("object_type", "TABLE") # Assume TABLE se não especificado
        key_type = object_type + "S" # TABLES ou VIEWS
        draft_metadata[key_type][object_name] = {"COLUMNS": {}}
        object_iterator.set_postfix_str(f"Processando {object_type}: {object_name}")

        # 1. Gerar descrição para a Tabela/View
        col_names_list = [col.get('name', '') for col in object_info.get('columns', [])]
        prompt_object = (
            f"Sugira uma descrição concisa em português brasileiro para um(a) {object_type} de banco de dados "
            f"chamado(a) '{object_name}'. "
            f"As colunas são: {', '.join(col_names_list[:10])}... "
            f"Foque no propósito provável do negócio. Responda apenas com a descrição sugerida."
        )
        object_description = generate_ai_description(prompt_object)
        draft_metadata[key_type][object_name]['description'] = object_description

        # 2. Gerar descrição para cada Coluna
        columns = object_info.get('columns', [])
        if columns:
            column_iterator = tqdm(columns, total=len(columns), desc=f"  -> Colunas de {object_name}", leave=False)
            for col in column_iterator:
                col_name = col.get('name')
                col_type = col.get('type')
                if not col_name or not col_type:
                    continue # Pula colunas sem nome ou tipo
                column_iterator.set_postfix_str(f"Processando coluna: {col_name}")

                prompt_column = (
                    f"Sugira uma descrição concisa em português brasileiro para a coluna de banco de dados chamada '{col_name}' "
                    f"do tipo '{col_type}' que pertence ao objeto '{object_name}'. "
                    f"Foque no significado provável do dado armazenado. Responda apenas com a descrição sugerida."
                )
                col_description = generate_ai_description(prompt_column)
                draft_metadata[key_type][object_name]['COLUMNS'][col_name] = {'description': col_description}
                # Não geramos 'value_mapping_notes' automaticamente

    # 3. Salvar o rascunho
    logger.info(f"Geração de rascunho concluída. Salvando em {OUTPUT_DRAFT_FILE}...")
    try:
        with open(OUTPUT_DRAFT_FILE, 'w', encoding='utf-8') as f:
            json.dump(draft_metadata, f, indent=4, ensure_ascii=False)
        logger.info(f"Rascunho de metadados salvo com sucesso em {OUTPUT_DRAFT_FILE}.")
    except IOError as e:
        logger.error(f"Erro de IO ao salvar o rascunho: {e}")
    except Exception as e:
        logger.exception("Erro inesperado ao salvar o rascunho:")

if __name__ == "__main__":
    main() 