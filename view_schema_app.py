import streamlit as st
import json
import pandas as pd
import fdb
import logging
import os
from collections import defaultdict
import re # Necessário para limpar o nome do tipo
# Importar a função de chat do nosso cliente Ollama
from src.ollama_integration.client import chat_completion

# Configuração do Logging (opcional para Streamlit, mas útil para depuração)
# Nível DEBUG para ver dados brutos da amostra
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

SCHEMA_FILE = "firebird_schema.json"
METADATA_FILE = "schema_metadata.json" # Novo arquivo para metadados

# --- Configurações Padrão --- (Podem ser sobrescritas na interface)
DEFAULT_DB_PATH = r"C:\Projetos\DADOS.FDB"
DEFAULT_DB_USER = "SYSDBA"
DEFAULT_DB_CHARSET = "WIN1252"
DEFAULT_SAMPLE_SIZE = 10

# --- Dicionário de Explicações de Tipos SQL (pt-br) ---
TYPE_EXPLANATIONS = {
    "INTEGER": "Número inteiro (sem casas decimais).",
    "VARCHAR": "Texto de tamanho variável.",
    "CHAR": "Texto de tamanho fixo.",
    "DATE": "Data (ano, mês, dia).",
    "TIMESTAMP": "Data e hora.",
    "BLOB": "Dados binários grandes (ex: imagem, texto longo).",
    "SMALLINT": "Número inteiro pequeno.",
    "BIGINT": "Número inteiro grande.",
    "FLOAT": "Número de ponto flutuante (aproximado).",
    "DOUBLE PRECISION": "Número de ponto flutuante com maior precisão.",
    "NUMERIC": "Número decimal exato (precisão definida).",
    "DECIMAL": "Número decimal exato (precisão definida).",
    "TIME": "Hora (hora, minuto, segundo)."
    # Adicionar outros tipos comuns se necessário
}

def get_type_explanation(type_string):
    """Tenta encontrar uma explicação para o tipo SQL base."""
    if not type_string:
        return ""
    # Extrai o nome base do tipo (ex: VARCHAR de VARCHAR(100))
    base_type = re.match(r"^([A-Z\s_]+)", type_string.upper())
    if base_type:
        explanation = TYPE_EXPLANATIONS.get(base_type.group(1).strip())
        return f"*{explanation}*" if explanation else ""
    return ""

# --- Funções Auxiliares --- 

@st.cache_data # Cache para estrutura técnica (não muda na sessão)
def load_schema(file_path):
    """Carrega o esquema técnico do banco de dados do arquivo JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Erro: Arquivo de esquema '{file_path}' não encontrado. Execute 'extract_firebird_schema.py' primeiro.")
        return None
    except json.JSONDecodeError:
        st.error(f"Erro: Arquivo de esquema '{file_path}' não é um JSON válido.")
        return None
    except Exception as e:
        st.error(f"Erro inesperado ao carregar o esquema: {e}")
        return None

def load_metadata(file_path):
    """Carrega os metadados (descrições) do arquivo JSON. Retorna dict vazio se não existir."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.warning(f"Aviso: Arquivo de metadados '{file_path}' inválido. Começando com metadados vazios.")
            return {}
        except Exception as e:
            st.error(f"Erro inesperado ao carregar metadados: {e}")
            return {}
    else:
        st.info(f"Arquivo de metadados '{file_path}' não encontrado. Será criado ao salvar.")
        return {}

def save_metadata_to_file(metadata, file_path):
    """Salva o dicionário de metadados no arquivo JSON."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        logger.info(f"Metadados salvos com sucesso em {file_path}")
        return True
    except IOError as e:
        logger.error(f"Erro de IO ao salvar metadados em {file_path}: {e}")
        st.error(f"Erro ao salvar arquivo de metadados: {e}")
        return False
    except Exception as e:
        logger.exception(f"Erro inesperado ao salvar metadados:")
        st.error(f"Erro inesperado ao salvar metadados: {e}")
        return False

def display_constraints(constraints):
    """Formata e exibe as constraints de uma tabela."""
    if not constraints:
        st.write("Nenhuma constraint definida para esta tabela.")
        return

    if constraints.get('primary_key'):
        st.subheader("Chave Primária")
        for pk in constraints['primary_key']:
            st.write(f"- Nome: `{pk['name']}`")
            st.write(f"  Colunas: `{', '.join(pk['columns'])}`")

    if constraints.get('foreign_keys'):
        st.subheader("Chaves Estrangeiras")
        for fk in constraints['foreign_keys']:
            st.write(f"- Nome: `{fk['name']}`")
            st.write(f"  Colunas: `{', '.join(fk['columns'])}`")
            st.write(f"  Referencia Tabela: `{fk['references_table']}`")
            # st.write(f"    Update Rule: {fk['update_rule']}") # Descomentar se precisar
            # st.write(f"    Delete Rule: {fk['delete_rule']}") # Descomentar se precisar

    if constraints.get('unique'):
        st.subheader("Constraints Únicas")
        for uq in constraints['unique']:
            st.write(f"- Nome: `{uq['name']}`")
            st.write(f"  Colunas: `{', '.join(uq['columns'])}`")

    if constraints.get('check'):
        st.subheader("Constraints Check")
        for ck in constraints['check']:
            st.write(f"- Nome: `{ck['name']}`")
            st.write(f"  Expressão: `{ck['expression']}`")

    # Adicionar outros tipos se necessário (ex: 'not_null', 'other')

def fetch_sample_data(db_path, user, password, charset, table_name, sample_size):
    """Busca uma amostra de dados de uma tabela ou view específica no Firebird."""
    conn = None
    try:
        logger.info(f"Tentando conectar a {db_path} para buscar amostra de {table_name}")
        conn = fdb.connect(
            dsn=db_path,
            user=user,
            password=password,
            charset=charset
        )
        cur = conn.cursor()
        sql = f'SELECT FIRST {sample_size} * FROM "{table_name}"'
        logger.info(f"Executando SQL: {sql}")
        cur.execute(sql)
        colnames = [desc[0] for desc in cur.description]
        logger.debug(f"Nomes das colunas da amostra: {colnames}")
        data = cur.fetchall()
        # Log DEBUG para ver os dados brutos antes de criar DataFrame
        logger.debug(f"Dados brutos recuperados ({len(data)} linhas): {data}")

        if not data:
            logger.info("Consulta de amostra não retornou linhas.")
            return pd.DataFrame(columns=colnames) # Retorna DF vazio com colunas

        # Tenta criar DataFrame
        df = pd.DataFrame(data, columns=colnames)
        logger.info(f"{len(df)} linhas de amostra convertidas para DataFrame.")
        return df

    except fdb.Error as e:
        logger.error(f"Erro do Firebird ao buscar amostra: {e}", exc_info=True)
        st.error(f"Erro de Conexão/Consulta Firebird: {e}")
        return None
    except Exception as e:
        logger.exception("Erro inesperado ao buscar/processar amostra de dados:")
        st.error(f"Erro inesperado ao processar dados: {e}")
        return None
    finally:
        if conn:
            conn.close()
            logger.info("Conexão para busca de amostra fechada.")

# Função para gerar descrição via IA (copiada e adaptada)
def generate_ai_description(prompt):
    """Chama a API Ollama para gerar uma descrição e limpa a resposta."""
    logger.debug(f"Enviando prompt para IA: {prompt}")
    messages = [{"role": "user", "content": prompt}]
    try:
        # Usando um spinner para feedback visual durante a chamada da IA
        with st.spinner("🧠 Pensando..."):
            response = chat_completion(messages=messages, stream=False)
        if response:
            cleaned_response = response.strip().strip('"').strip('\'').strip()
            logger.debug(f"Resposta da IA (limpa): {cleaned_response}")
            return cleaned_response
        else:
            logger.warning("Falha ao obter descrição da IA (resposta vazia).")
            st.toast("😕 A IA não retornou uma sugestão.")
            return None
    except Exception as e:
        logger.exception("Erro ao chamar a API Ollama:")
        st.error(f"Erro ao contatar a IA: {e}")
        return None

# --- Inicialização do Estado da Sessão (AGORA DEPOIS DAS FUNÇÕES) --- 
if 'db_password' not in st.session_state:
    st.session_state.db_password = "" # Senha não usada mais aqui, mas mantendo por consistência
if 'metadata' not in st.session_state:
    # Carrega metadados na inicialização da sessão
    # Agora load_metadata já está definida
    st.session_state.metadata = load_metadata(METADATA_FILE)
    logger.info("Metadados carregados para session_state na inicialização.")

# --- Função Principal da Aplicação --- 
def main():
    st.set_page_config(page_title="Anotador de Esquema Firebird", layout="wide")
    st.title("📝 Anotador de Esquema Firebird")

    # Garante que metadados estão no estado da sessão (se não, recarrega)
    # Esta verificação pode ser redundante devido à inicialização acima, mas segura
    if 'metadata' not in st.session_state:
        st.session_state.metadata = load_metadata(METADATA_FILE)
        logger.info("Metadados (re)carregados para session_state dentro de main.")

    schema_data = load_schema(SCHEMA_FILE)
    if not schema_data:
        st.stop()

    # --- Barra Lateral --- 
    st.sidebar.header("Configurações de Conexão (Amostra)")
    db_path_input = st.sidebar.text_input("Caminho DB (.fdb)", value=DEFAULT_DB_PATH)
    db_user_input = st.sidebar.text_input("Usuário DB", value=DEFAULT_DB_USER)
    # Senha não fica na sidebar, será pedida no expander

    st.sidebar.divider()
    # Botão Salvar na Sidebar
    if st.sidebar.button("💾 Salvar Metadados", use_container_width=True):
        if save_metadata_to_file(st.session_state.metadata, METADATA_FILE):
            st.sidebar.success("Metadados salvos com sucesso!")
            # Limpar cache de load_metadata não é necessário pois está na session_state
        else:
            st.sidebar.error("Falha ao salvar metadados.")
    st.sidebar.caption(f"Os metadados serão salvos em: {METADATA_FILE}")
    sample_size_input = st.sidebar.number_input("Tamanho da Amostra (Preview/Final)", min_value=1, max_value=100, value=DEFAULT_SAMPLE_SIZE)

    # --- Conteúdo Principal ---
    st.subheader("Filtro de Objetos")
    filter_type = st.radio(
        "Mostrar:",
        ("Todos", "Tabelas", "Views"),
        horizontal=True,
        label_visibility="collapsed"
    )

    # Filtrar object_names com base na seleção do rádio
    all_object_names = sorted(list(schema_data.keys()))
    if filter_type == "Tabelas":
        object_names = [name for name in all_object_names if schema_data[name].get("object_type") == "TABLE"]
    elif filter_type == "Views":
        object_names = [name for name in all_object_names if schema_data[name].get("object_type") == "VIEW"]
    else: # "Todos"
        object_names = all_object_names

    if not object_names:
        st.warning(f"Nenhum objeto do tipo '{filter_type}' encontrado no arquivo de esquema.")
        st.stop()

    selected_object = st.selectbox("Selecione uma Tabela ou View para anotar:", object_names)

    # --- Lógica ao Selecionar Objeto --- 
    if selected_object:
        object_info = schema_data[selected_object]
        object_type = object_info.get("object_type", "TABLE")
        key_type = object_type + "S"
        st.header(f"Anotando: `{selected_object}` ({object_type})")

        # **NOVO: Buscar amostra ao selecionar o objeto e guardar no session_state**
        sample_data_key = f"sample_data_{selected_object}"
        if sample_data_key not in st.session_state:
            logger.info(f"Buscando amostra para {selected_object} pela primeira vez nesta sessão.")
            # Usar senha hardcoded
            password_to_use = "M@nagers2023"
            with st.spinner(f"Buscando amostra de dados para {selected_object}..."):
                 st.session_state[sample_data_key] = fetch_sample_data(
                    db_path=db_path_input,
                    user=db_user_input,
                    password=password_to_use,
                    charset=DEFAULT_DB_CHARSET,
                    table_name=selected_object,
                    sample_size=sample_size_input # Usa o tamanho da sidebar
                )
        # Recupera a amostra do estado da sessão (pode ser None se falhou)
        sample_df = st.session_state.get(sample_data_key, None)
        if sample_df is None:
            st.warning(f"Não foi possível carregar amostra de dados para '{selected_object}'. Verifique a conexão ou logs.")
        elif sample_df.empty:
             st.info(f"Amostra de dados para '{selected_object}' está vazia (0 linhas retornadas).")

        # --- Anotação da Tabela/View ---
        st.subheader("Descrição Geral do Objeto")
        # Garante estrutura no session_state
        st.session_state.metadata.setdefault(key_type, {})
        st.session_state.metadata[key_type].setdefault(selected_object, {})
        st.session_state.metadata[key_type][selected_object].setdefault('description', '')

        col1, col2 = st.columns([4, 1]) # Coluna maior para text area, menor para botão
        with col1:
            table_desc_key = f"desc_{object_type}_{selected_object}"
            st.session_state.metadata[key_type][selected_object]['description'] = st.text_area(
                label="Descreva o propósito desta tabela/view:",
                value=st.session_state.metadata[key_type][selected_object]['description'],
                key=table_desc_key,
                height=100
            )
        with col2:
             # Botão para sugerir descrição da tabela/view
             if st.button("Sugerir (IA)", key=f"btn_ai_desc_{selected_object}", use_container_width=True):
                st.write("Gerando...") # Feedback visual temporário
                col_names_list = [col.get('name', '') for col in object_info.get('columns', [])]
                prompt_object = (
                    f"Sugira uma descrição concisa em português brasileiro para um(a) {object_type} de banco de dados "
                    f"chamado(a) '{selected_object}'. "
                    f"As colunas são: {', '.join(col_names_list[:10])}... "
                    f"Foque no propósito provável do negócio. Responda apenas com a descrição sugerida."
                )
                suggestion = generate_ai_description(prompt_object)
                if suggestion:
                    st.session_state.metadata[key_type][selected_object]['description'] = suggestion
                    st.rerun() # Força rerodar para atualizar o text_area com a sugestão

        # **NOVO: Botão para sugerir todas as colunas**
        st.markdown("--- Sugestão para Todas as Colunas ---")
        if st.button("Sugerir Todas as Colunas (IA)", key=f"btn_ai_all_cols_{selected_object}", help="Pede sugestões de descrição para todas as colunas listadas abaixo."):
            columns_to_process = object_info.get('columns', [])
            if not columns_to_process:
                st.toast("Nenhuma coluna encontrada para gerar sugestões.")
            else:
                progress_bar = st.progress(0, text="Gerando sugestões para colunas...")
                total_cols = len(columns_to_process)
                for i, col in enumerate(columns_to_process):
                    col_name = col.get('name')
                    col_type = col.get('type')
                    if not col_name or not col_type:
                        continue

                    # Atualiza texto da barra de progresso
                    progress_text = f"Gerando sugestões para colunas... ({i+1}/{total_cols}: {col_name})"
                    progress_bar.progress((i + 1) / total_cols, text=progress_text)

                    # Gera o prompt específico para a coluna
                    prompt_column = (
                        f"Sugira uma descrição concisa em português brasileiro para a coluna de banco de dados chamada '{col_name}' "
                        f"do tipo '{col_type}' que pertence ao objeto '{selected_object}' ({object_type}). "
                        f"Foque no significado provável do dado armazenado. Responda apenas com a descrição sugerida."
                    )
                    # Chama a IA (sem spinner individual, pois temos a barra de progresso)
                    # Modificar generate_ai_description para não usar spinner interno ou criar uma versão sem spinner?
                    # Por enquanto, manteremos o spinner interno, pode ficar um pouco repetitivo visualmente.
                    suggestion = generate_ai_description(prompt_column)

                    # Atualiza o estado da sessão com a sugestão (mesmo se for None ou erro, para registrar)
                    if suggestion:
                         st.session_state.metadata.setdefault(key_type, {}).setdefault(selected_object, {}).setdefault('COLUMNS', {}).setdefault(col_name, {})['description'] = suggestion
                    else: # Se falhar, não sobrescreve descrição existente
                         logger.warning(f"Não foi possível gerar sugestão para a coluna {col_name}")

                progress_bar.progress(1.0, text="Sugestões de colunas concluídas!")
                st.toast("Sugestões para todas as colunas foram geradas!")
                # Pequena pausa para o usuário ver a mensagem final da barra
                import time
                time.sleep(1)
                st.rerun() # Reroda para exibir todas as sugestões nos campos

        # --- Anotação das Colunas ---
        st.subheader("Colunas e Descrições")
        if object_info.get('columns'):
            st.session_state.metadata[key_type][selected_object].setdefault('COLUMNS', {})
            for col in object_info['columns']:
                col_name = col['name']
                col_type = col['type']
                col_nullable = col['nullable']

                st.session_state.metadata[key_type][selected_object]['COLUMNS'].setdefault(col_name, {})
                st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name].setdefault('description', '')
                st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name].setdefault('value_mapping_notes', '')

                # Exibe nome, tipo e explicação
                type_explanation = get_type_explanation(col_type)
                markdown_string = f"**`{col_name}`** (`{col_type}`){' - *NOT NULL*' if not col_nullable else ''}"
                if type_explanation:
                    markdown_string += f" - {type_explanation}"
                st.markdown(markdown_string)
                
                # **NOVO: Mostrar exemplos de dados da coluna (se disponíveis)**
                if sample_df is not None and not sample_df.empty and col_name in sample_df.columns:
                    try:
                        # Pega até 3 valores únicos não nulos
                        unique_values = sample_df[col_name].dropna().unique()
                        examples = [str(v) for v in unique_values[:3]] # Converte para string
                        if examples:
                            st.caption(f"Exemplos: `{'`, `'.join(examples)}`")
                        else:
                            st.caption("Exemplos: (Amostra sem valores não nulos para esta coluna)")
                    except Exception as e:
                        logger.warning(f"Erro ao processar exemplos para coluna {col_name}: {e}")
                        st.caption("Exemplos: (Erro ao buscar)")
                # Fim do bloco de exemplos
                
                # Layout para descrição da coluna e botão IA
                col_desc_area, col_btn_area = st.columns([4,1])
                with col_desc_area:
                    col_key = f"desc_col_{selected_object}_{col_name}"
                    st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name]['description'] = st.text_area(
                        label=f"Descrição para `{col_name}`:",
                        value=st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name]['description'],
                        key=col_key,
                        label_visibility="collapsed",
                        height=75
                    )
                with col_btn_area:
                    # Botão para sugerir descrição da coluna
                    if st.button("Sugerir (IA)", key=f"btn_ai_col_{selected_object}_{col_name}", use_container_width=True):
                        st.write("Gerando...") # Feedback temporário
                        prompt_column = (
                            f"Sugira uma descrição concisa em português brasileiro para a coluna de banco de dados chamada '{col_name}' "
                            f"do tipo '{col_type}' que pertence ao objeto '{selected_object}' ({object_type}). "
                            f"Foque no significado provável do dado armazenado. Responda apenas com a descrição sugerida."
                        )
                        suggestion = generate_ai_description(prompt_column)
                        if suggestion:
                            st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name]['description'] = suggestion
                            st.rerun()

                st.caption("Acima: Descrição geral. Abaixo: Mapeamento de valores.") # Legenda ajustada
                st.markdown("--- Optional: Value Mappings ---")
                map_key = f"map_notes_{selected_object}_{col_name}"
                st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name]['value_mapping_notes'] = st.text_area(
                    label=f"Notas sobre mapeamento de valores para `{col_name}` (Ex: 1: Ativo, 2: Inativo):",
                    value=st.session_state.metadata[key_type][selected_object]['COLUMNS'][col_name]['value_mapping_notes'],
                    key=map_key,
                    label_visibility="collapsed",
                    height=75
                )
                st.divider()
        else:
            st.write("Nenhuma coluna definida para este objeto.")

        # --- Exibição de Constraints e Amostra (sem anotação direta aqui) ---
        if object_info.get('constraints') or object_type == "TABLE":
             st.subheader("Constraints" + (" (Info)" if object_type == "VIEW" else ""))
             display_constraints(object_info.get('constraints'))

        # --- Amostra de Dados Completa (Permanece igual, mas agora usa dados do state se disponíveis) ---
        st.divider()
        st.header("Amostra de Dados Completa (Visualização)")
        with st.expander(f"Mostrar as primeiras {sample_size_input} linhas de `{selected_object}`?"):
            # Verifica se já temos a amostra no state
            if sample_df is not None:
                if not sample_df.empty:
                    st.dataframe(sample_df, use_container_width=True)
                else:
                    st.info(f"A consulta original para '{selected_object}' retornou 0 linhas.")
            else:
                # Se não estava no state (erro anterior), mostra o aviso
                 st.warning(f"Não foi possível carregar a amostra de dados para '{selected_object}' ao selecionar o objeto.")
                # Poderia adicionar um botão para tentar recarregar aqui, mas complica

if __name__ == "__main__":
    main() 