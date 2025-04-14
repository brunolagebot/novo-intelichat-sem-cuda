import streamlit as st
import json
import pandas as pd
import fdb
import logging
import os
from collections import defaultdict
import re # Necessário para limpar o nome do tipo
import datetime # NOVO: Para timestamps
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

# --- Constante para arquivo de timestamps ---
RUN_TIMES_FILE = "run_times.json"

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

def find_existing_description(metadata, target_col_name):
    """Procura por uma descrição existente para um nome de coluna em todo o metadado."""
    if not metadata or not target_col_name:
        return None
    # Procura em Tabelas
    for table_name, table_meta in metadata.get('TABLES', {}).items():
        col_meta = table_meta.get('COLUMNS', {}).get(target_col_name)
        if col_meta and col_meta.get('description'):
            logger.debug(f"Encontrada descrição existente para '{target_col_name}' na tabela '{table_name}'")
            return col_meta['description']
    # Procura em Views
    for view_name, view_meta in metadata.get('VIEWS', {}).items():
        col_meta = view_meta.get('COLUMNS', {}).get(target_col_name)
        if col_meta and col_meta.get('description'):
            logger.debug(f"Encontrada descrição existente para '{target_col_name}' na view '{view_name}'")
            return col_meta['description']
    return None # Não encontrado

# --- Função para Contar Linhas (Reintroduzida) ---
def fetch_row_count(db_path, user, password, charset, table_name):
    """Busca a contagem de linhas de uma tabela/view específica no Firebird."""
    conn = None
    try:
        logger.info(f"Buscando contagem de linhas para {table_name}")
        conn = fdb.connect(dsn=db_path, user=user, password=password, charset=charset)
        cur = conn.cursor()
        sql = f'SELECT COUNT(*) FROM "{table_name}"'
        cur.execute(sql)
        count = cur.fetchone()[0] # Pega o primeiro (e único) valor da primeira linha
        logger.info(f"Contagem para {table_name}: {count}")
        return count
    except fdb.Error as e:
        logger.error(f"Erro do Firebird ao buscar contagem para {table_name}: {e}", exc_info=True)
        # Retorna a string de erro em vez de -1 para exibição na tabela
        return f"Erro DB: {e.args[0] if e.args else e}"
    except Exception as e:
        logger.exception(f"Erro inesperado ao buscar contagem para {table_name}:")
        # Retorna a string de erro
        return f"Erro inesperado: {e}"
    finally:
        if conn:
            conn.close()
            logger.debug(f"Conexão para busca de contagem ({table_name}) fechada.")

# --- NOVA FUNÇÃO: Gerar Visão Geral da Documentação ---
# (Adaptada para esta versão - sem cache, sem contar linhas reais)
def generate_documentation_overview(schema_data):
    """
    Analisa os metadados carregados e gera um DataFrame com o status da documentação
    para cada tabela e view.
    """
    logger.info("Iniciando generate_documentation_overview...")
    overview_data = []
    # Nesta versão, schema_data vem de load_schema e não tem TABLES/VIEWS separados
    # Iteramos diretamente sobre as chaves do schema_data
    
    total_objects_processed = 0
    for name, info in schema_data.items():
        object_type = info.get('object_type', 'DESCONHECIDO') # Pega tipo do schema
        # Não processa se não for TABLE ou VIEW (ex: constraints soltas)
        if object_type not in ["TABLE", "VIEW"]:
             continue

        logger.debug(f"Processando objeto: {name} (Tipo: {object_type})")
        total_objects_processed += 1
        columns = info.get('columns', []) # É uma lista de dicts nesta versão
        total_cols = len(columns)
        
        # Precisamos carregar metadados para contar descrições/notas
        metadata = st.session_state.get('metadata', {}) # Pega metadados da sessão
        key_type = object_type + "S" # TABLES ou VIEWS
        object_meta = metadata.get(key_type, {}).get(name, {})
        object_columns_meta = object_meta.get('COLUMNS', {})
        
        described_cols = 0
        noted_cols = 0

        if total_cols > 0:
            for col_def in columns: # Itera sobre a definição do schema
                col_name = col_def.get('name')
                if col_name:
                    col_meta = object_columns_meta.get(col_name, {})
                    if col_meta.get('description', '').strip():
                        described_cols += 1
                    if col_meta.get('value_mapping_notes', '').strip():
                        noted_cols += 1
            
            desc_perc = (described_cols / total_cols) * 100
            notes_perc = (noted_cols / total_cols) * 100
        else:
            desc_perc = 0
            notes_perc = 0

        # Pega a contagem de linhas do estado da sessão, se disponível
        overview_counts = st.session_state.get("overview_row_counts", {})
        row_count_display = overview_counts.get(name, "N/A") # Pega do cache ou N/A
        # Formata se for número, mantém como está se for erro (string) ou N/A
        if isinstance(row_count_display, int) and row_count_display >= 0:
             row_count_display = f"{row_count_display:,}"

        overview_data.append({
            'Objeto': name,
            'Tipo': object_type,
            'Total Colunas': total_cols,
            'Total Linhas': row_count_display, # Usa valor do cache ou N/A
            'Colunas Descritas': described_cols,
            'Colunas com Notas': noted_cols,
            '% Descritas': f"{desc_perc:.1f}%",
            '% Com Notas': f"{notes_perc:.1f}%"
        })

    df_overview = pd.DataFrame(overview_data)
    # Ordenar por tipo e depois por nome do objeto
    if not df_overview.empty:
        df_overview = df_overview.sort_values(by=['Tipo', 'Objeto']).reset_index(drop=True)
    logger.info(f"generate_documentation_overview concluído. Total de objetos processados: {total_objects_processed}. Shape do DataFrame gerado: {df_overview.shape}")
    return df_overview

# --- NOVAS Funções Auxiliares para Timestamps ---
def load_run_times(file_path):
    """Carrega os timestamps de execução do arquivo JSON."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.warning(f"Aviso: Arquivo de timestamps '{file_path}' inválido. Começando vazio.")
            return {}
        except Exception as e:
            logging.error(f"Erro inesperado ao carregar timestamps: {e}")
            return {}
    else:
        return {}

def save_run_times(run_times_data, file_path):
    """Salva o dicionário de timestamps no arquivo JSON."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(run_times_data, f, indent=4)
        logging.info(f"Timestamps salvos com sucesso em {file_path}")
        return True
    except IOError as e:
        logging.error(f"Erro de IO ao salvar timestamps em {file_path}: {e}")
        st.error(f"Erro ao salvar arquivo de timestamps: {e}")
        return False
    except Exception as e:
        logging.error(f"Erro inesperado ao salvar timestamps: {e}")
        st.error(f"Erro inesperado ao salvar timestamps: {e}")
        return False

# --- Função Principal da Aplicação --- 
def main():
    st.set_page_config(page_title="Anotador de Esquema Firebird", layout="wide")
    
    # Garante que metadados e chaves principais estão no estado da sessão
    if 'metadata' not in st.session_state:
        st.session_state.metadata = load_metadata(METADATA_FILE)
        logger.info("Metadados (re)carregados para session_state dentro de main.")
    # Garante as chaves de nível superior toda vez que main rodar
    st.session_state.metadata.setdefault('TABLES', {})
    st.session_state.metadata.setdefault('VIEWS', {})
    st.session_state.metadata.setdefault('_GLOBAL_CONTEXT', 'Digite aqui informações gerais sobre a empresa, o propósito do banco de dados, etc.')

    # Inicializa o estado do modo de visualização
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = "Explorar Esquema"

    # NOVO: Carrega timestamps e inicializa cache de contagem
    if 'run_times' not in st.session_state:
        st.session_state.run_times = load_run_times(RUN_TIMES_FILE)
    if 'overview_row_counts' not in st.session_state:
         st.session_state.overview_row_counts = {} # Inicia cache de contagem vazio

    # Carrega o schema técnico (estrutura real do DB)
    schema_data = load_schema(SCHEMA_FILE)
    if not schema_data:
        st.stop()

    # --- Barra Lateral --- 
    st.sidebar.title("Navegação e Configurações") # Título ajustado
    
    # Seletor de Modo
    st.session_state.app_mode = st.sidebar.radio(
        "Modo de Visualização",
        ["Explorar Esquema", "Visão Geral da Documentação"],
        key='app_mode_selector',
        index=["Explorar Esquema", "Visão Geral da Documentação"].index(st.session_state.app_mode)
    )
    st.sidebar.divider()

    # Configurações de Conexão (Sempre visível nesta versão, pode ser necessário ajustar)
    st.sidebar.header("Configurações de Conexão")
    db_path_input = st.sidebar.text_input("Caminho DB (.fdb)", value=DEFAULT_DB_PATH, key="db_path_sb") # Chave diferente para evitar conflito com st.session_state
    db_user_input = st.sidebar.text_input("Usuário DB", value=DEFAULT_DB_USER, key="db_user_sb")
    # Senha não fica na sidebar
    
    st.sidebar.divider()
    # Contexto Geral
    st.sidebar.subheader("Contexto Geral")
    context_key = "global_context_input"
    current_global_context = st.session_state.metadata.get('_GLOBAL_CONTEXT', '')
    new_global_context = st.sidebar.text_area(
        "Descreva o contexto geral da empresa/dados:",
        value=current_global_context,
        key=context_key,
        height=150
    )
    if new_global_context != current_global_context:
        st.session_state.metadata['_GLOBAL_CONTEXT'] = new_global_context
        st.toast("Contexto global atualizado (não salvo)", icon="✏️")

    st.sidebar.divider()
    # Botão Salvar
    if st.sidebar.button("💾 Salvar Metadados e Contexto", use_container_width=True):
        if save_metadata_to_file(st.session_state.metadata, METADATA_FILE):
            st.sidebar.success("Metadados e Contexto salvos!")
            st.session_state.metadata = load_metadata(METADATA_FILE) # Recarrega
            st.toast("Metadados salvos!", icon="💾")
        else:
            st.sidebar.error("Falha ao salvar.")
    st.sidebar.caption(f"Salvo em: {METADATA_FILE}")

    # --- Conteúdo Principal (Condicional ao Modo) ---

    if st.session_state.app_mode == "Visão Geral da Documentação":
        st.title("Visão Geral da Documentação do Esquema")
        st.markdown("Acompanhe o progresso da documentação e contagem de linhas.") # Texto atualizado
        
        if schema_data:
             try:
                 # Gera e exibe a tabela (usará st.session_state.overview_row_counts se populado)
                 df_overview = generate_documentation_overview(schema_data)
                 st.dataframe(df_overview, use_container_width=True)
                 
                 st.divider()
                 # --- Botão e Lógica para Calcular Contagens --- 
                 if st.button("Calcular Contagem de Linhas (Todos)", key="btn_count_all"):
                      password_to_use = "M@nagers2023" # Senha hardcoded ainda
                      objects_to_count = df_overview['Objeto'].tolist() # Pega nomes da tabela gerada
                      total_obj = len(objects_to_count)
                      progress_bar = st.progress(0, text="Iniciando contagem de linhas...")
                      temp_counts = {} # Armazena contagens desta execução

                      with st.spinner(f"Calculando contagem para {total_obj} objetos..."): 
                          for i, obj_name in enumerate(objects_to_count):
                              progress_text = f"Contando {obj_name}... ({i+1}/{total_obj})"
                              progress_bar.progress((i + 1) / total_obj, text=progress_text)
                              logger.info(f"Executando fetch_row_count para: {obj_name}")
                              # Passa configs da sidebar para a função
                              count_result = fetch_row_count(
                                  db_path=db_path_input, user=db_user_input, 
                                  password=password_to_use, # Usar a senha correta
                                  charset=DEFAULT_DB_CHARSET, table_name=obj_name
                              )
                              temp_counts[obj_name] = count_result # Armazena resultado (int ou erro)
                      
                      # Atualiza estado da sessão e timestamp
                      st.session_state.overview_row_counts = temp_counts
                      now_iso = datetime.datetime.now().isoformat()
                      st.session_state.run_times['last_row_count_all'] = now_iso
                      save_run_times(st.session_state.run_times, RUN_TIMES_FILE)
                      progress_bar.progress(1.0, text="Contagem concluída!")
                      st.toast("Contagem de linhas concluída e salva!")
                      time.sleep(1) # Pausa para ver msg
                      st.rerun() # Re-executa para mostrar os resultados na tabela
                 
                 # --- Exibe Última Execução --- 
                 last_run = st.session_state.run_times.get('last_row_count_all')
                 if last_run:
                      # Tenta formatar para melhor leitura, se falhar mostra ISO
                      try:
                          dt_obj = datetime.datetime.fromisoformat(last_run)
                          last_run_display = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
                      except ValueError:
                           last_run_display = last_run
                      st.caption(f"Última contagem completa realizada em: {last_run_display}")
                 else:
                      st.caption("Contagem completa de linhas ainda não foi realizada.")

                 # Adiciona legenda
                 st.subheader("Legenda:")
                 st.markdown("""
                 *   **Objeto:** Nome da Tabela ou View.
                 *   **Tipo:** Indica se é TABLE ou VIEW.
                 *   **Total Colunas:** Número total de colunas no objeto (do schema técnico).
                 *   **Total Linhas:** Contagem real não implementada (N/A).
                 *   **Colunas Descritas:** Número de colunas com `description` preenchido nos metadados.
                 *   **Colunas com Notas:** Número de colunas com `value_mapping_notes` preenchido nos metadados.
                 *   **% Descritas / % Com Notas:** Percentuais correspondentes.
                 """)
             except Exception as e:
                 st.error(f"Erro ao gerar a visão geral da documentação: {e}")
                 logger.exception("Erro em generate_documentation_overview:")
        else:
             st.warning("Esquema técnico não carregado. Não é possível gerar a visão geral.")

    elif st.session_state.app_mode == "Explorar Esquema":
        st.title("📝 Anotador de Esquema Firebird") # Título do modo original
        
        # --- Filtro e Seletor de Objetos (Lógica existente) ---
        st.subheader("Filtro de Objetos")
        filter_type = st.radio(
            "Mostrar:",
            ("Todos", "Tabelas", "Views"),
            horizontal=True,
            label_visibility="collapsed"
        )
        # Filtrar object_names com base na seleção do rádio (usando schema_data técnico)
        all_object_names = sorted(list(schema_data.keys()))
        object_names = []
        if filter_type == "Tabelas":
            object_names = [name for name in all_object_names if schema_data[name].get("object_type") == "TABLE"]
        elif filter_type == "Views":
            object_names = [name for name in all_object_names if schema_data[name].get("object_type") == "VIEW"]
        else: # "Todos"
            # Inclui apenas TABLE e VIEW (ignora outros tipos que possam existir no schema_data)
            object_names = [name for name in all_object_names if schema_data[name].get("object_type") in ["TABLE", "VIEW"]]

        if not object_names:
            st.warning(f"Nenhum objeto do tipo '{filter_type}' encontrado no arquivo de esquema.")
            st.stop()
        
        selected_object = st.selectbox("Selecione uma Tabela ou View para anotar:", object_names)
        
        # --- Lógica ao Selecionar Objeto (Lógica existente adaptada) ---
        if selected_object:
            if st.session_state.get('last_displayed_sample_object') != selected_object:
                st.session_state.sample_display_df = None
                st.session_state.last_displayed_sample_object = selected_object

            object_info = schema_data[selected_object] # Info técnica
            object_type = object_info.get("object_type", "TABLE")
            key_type = object_type + "S" # Para acessar metadados
            
            st.header(f"Anotando: `{selected_object}` ({object_type})")
            st.divider()
            
            # --- Seção de Amostra de Dados (com botões) ---
            with st.expander(f"Visualizar Amostra de Dados de '{selected_object}'", expanded=False):
                st.write("**Buscar Amostra:**")
                sample_sizes = [10, 50, 100, 500, 1000, 5000]
                cols_buttons = st.columns(len(sample_sizes))
                password_to_use = "M@nagers2023"
                for i, size in enumerate(sample_sizes):
                    with cols_buttons[i]:
                        if st.button(f"{size} linhas", key=f"btn_fetch_display_sample_{size}_{selected_object}", use_container_width=True):
                            with st.spinner(f"Buscando {size} linhas para visualização..."):
                                st.session_state.sample_display_df = fetch_sample_data(
                                    db_path=db_path_input, user=db_user_input, password=password_to_use,
                                    charset=DEFAULT_DB_CHARSET, table_name=selected_object,
                                    sample_size=size
                                )
                                st.rerun()
                st.divider()
                if isinstance(st.session_state.get('sample_display_df'), pd.DataFrame):
                    df_to_show = st.session_state.sample_display_df
                    st.info(f"Exibindo {len(df_to_show)} linhas.")
                    if not df_to_show.empty:
                        st.dataframe(df_to_show, use_container_width=True)
                    else:
                        st.info("A consulta da amostra não retornou linhas.")
                elif isinstance(st.session_state.get('sample_display_df'), str):
                    st.error(f"Erro ao buscar amostra: {st.session_state.sample_display_df}")
                else:
                    st.caption("Clique em um dos botões acima para buscar e exibir uma amostra dos dados.")
            st.divider()

            # --- Busca de Amostra para Exemplos (Lógica existente) ---
            sample_data_key = f"sample_data_{selected_object}"
            if sample_data_key not in st.session_state:
                 logger.info(f"Buscando amostra para {selected_object} pela primeira vez nesta sessão.")
                 password_to_use_ex = "M@nagers2023"
                 with st.spinner(f"Buscando amostra de dados para {selected_object}..."):
                     st.session_state[sample_data_key] = fetch_sample_data(
                        db_path=db_path_input, user=db_user_input, password=password_to_use_ex,
                        charset=DEFAULT_DB_CHARSET, table_name=selected_object, sample_size=DEFAULT_SAMPLE_SIZE
                     )
            sample_df = st.session_state.get(sample_data_key, None)
            # Removida exibição duplicada da amostra preview aqui

            # --- Anotação da Tabela/View (Lógica existente) ---
            st.subheader("Descrição Geral do Objeto")
            if key_type not in st.session_state.metadata: st.session_state.metadata[key_type] = {}
            if selected_object not in st.session_state.metadata[key_type]: st.session_state.metadata[key_type][selected_object] = {}
            if 'description' not in st.session_state.metadata[key_type][selected_object]: st.session_state.metadata[key_type][selected_object]['description'] = ''
            if 'COLUMNS' not in st.session_state.metadata[key_type][selected_object]: st.session_state.metadata[key_type][selected_object]['COLUMNS'] = {}
            col1, col2 = st.columns([4, 1])
            with col1:
                table_desc_key = f"desc_{object_type}_{selected_object}"
                st.session_state.metadata[key_type][selected_object]['description'] = st.text_area(
                    label="Descreva o propósito desta tabela/view:",
                    value=st.session_state.metadata[key_type][selected_object]['description'],
                    key=table_desc_key, height=100)
            with col2:
                 if st.button("Sugerir (IA)", key=f"btn_ai_desc_{selected_object}", use_container_width=True):
                    col_names_list = [col.get('name', '') for col in object_info.get('columns', [])]
                    prompt_object = (
                        f"Sugira uma descrição concisa em português brasileiro para um(a) {object_type} de banco de dados "
                        f"chamado(a) '{selected_object}'. As colunas são: {', '.join(col_names_list[:10])}... "
                        f"Foque no propósito provável do negócio. Responda apenas com a descrição sugerida.")
                    suggestion = generate_ai_description(prompt_object)
                    if suggestion:
                        st.session_state.metadata[key_type][selected_object]['description'] = suggestion
                        st.rerun()

            # --- Botão Sugerir Todas as Colunas (Lógica existente) ---
            st.markdown("--- Sugestão para Todas as Colunas ---")
            if st.button("Sugerir Todas as Colunas (IA)", key=f"btn_ai_all_cols_{selected_object}", help="Pede sugestões de descrição para todas as colunas listadas abaixo."):
                 columns_to_process = object_info.get('columns', [])
                 if not columns_to_process: st.toast("Nenhuma coluna encontrada para gerar sugestões.")
                 else:
                     progress_bar = st.progress(0, text="Gerando sugestões para colunas...")
                     total_cols = len(columns_to_process)
                     for i, col in enumerate(columns_to_process):
                         col_name = col.get('name'); col_type = col.get('type')
                         if not col_name or not col_type: continue
                         progress_text = f"Gerando sugestões para colunas... ({i+1}/{total_cols}: {col_name})"
                         progress_bar.progress((i + 1) / total_cols, text=progress_text)
                         prompt_column = (f"Sugira uma descrição concisa em português brasileiro para a coluna '{col_name}' ({col_type}) do objeto '{selected_object}' ({object_type}). Foque no significado. Responda só a descrição.")
                         suggestion = generate_ai_description(prompt_column)
                         if suggestion: st.session_state.metadata.setdefault(key_type, {}).setdefault(selected_object, {}).setdefault('COLUMNS', {}).setdefault(col_name, {})['description'] = suggestion
                         else: logger.warning(f"Não foi possível gerar sugestão para a coluna {col_name}")
                     progress_bar.progress(1.0, text="Sugestões concluídas!"); st.toast("Sugestões geradas!"); import time; time.sleep(1); st.rerun()


            # --- Anotação das Colunas (Lógica existente) ---
            st.subheader("Colunas, Exemplos e Descrições")
            if object_info.get('columns'):
                object_columns_metadata = st.session_state.metadata[key_type][selected_object]['COLUMNS']
                for col in object_info['columns']:
                    col_name = col['name']; col_type = col['type']; col_nullable = col['nullable']
                    if col_name not in object_columns_metadata: object_columns_metadata[col_name] = {}
                    current_col_metadata = object_columns_metadata[col_name]
                    if 'description' not in current_col_metadata: current_col_metadata['description'] = ''
                    if 'value_mapping_notes' not in current_col_metadata: current_col_metadata['value_mapping_notes'] = ''
                    type_explanation = get_type_explanation(col_type)
                    markdown_string = f"**`{col_name}`** (`{col_type}`){' - *NOT NULL*' if not col_nullable else ''}"
                    if type_explanation: markdown_string += f" - {type_explanation}"
                    st.markdown(markdown_string)
                    if sample_df is not None and not sample_df.empty and col_name in sample_df.columns:
                        try:
                            unique_values = sample_df[col_name].dropna().unique()
                            examples = [str(v) for v in unique_values[:3]]
                            if examples: st.caption(f"Exemplos: `{'`, `'.join(examples)}`")
                            else: st.caption("Exemplos: (Amostra sem valores não nulos)")
                        except Exception as e: logger.warning(f"Erro ao processar exemplos: {e}"); st.caption("Exemplos: (Erro)")
                    description_value = current_col_metadata['description']
                    if not description_value: existing_desc = find_existing_description(st.session_state.metadata, col_name); description_value = existing_desc or description_value
                    col_desc_area, col_btn_area = st.columns([4,1])
                    with col_desc_area:
                        col_key = f"desc_col_{selected_object}_{col_name}"
                        current_col_metadata['description'] = st.text_area(label=f"Descrição para `{col_name}`:", value=description_value, key=col_key, label_visibility="collapsed", height=75)
                    with col_btn_area:
                        if st.button("Sugerir (IA)", key=f"btn_ai_col_{selected_object}_{col_name}", use_container_width=True):
                            prompt_column = (f"Sugira descrição concisa pt-br para coluna '{col_name}' ({col_type}) do objeto '{selected_object}' ({object_type}). Significado? Responda só descrição.")
                            suggestion = generate_ai_description(prompt_column)
                            if suggestion: current_col_metadata['description'] = suggestion; st.rerun()
                    st.caption("Acima: Descrição. Abaixo: Mapeamento."); st.markdown("--- Mapeamento ---")
                    map_key = f"map_notes_{selected_object}_{col_name}"
                    current_col_metadata['value_mapping_notes'] = st.text_area(label=f"Notas mapeamento `{col_name}`:", value=current_col_metadata['value_mapping_notes'], key=map_key, label_visibility="collapsed", height=75)
                    st.divider()
            else: st.write("Nenhuma coluna definida.")

            # --- Exibição de Constraints (Lógica existente) ---
            if object_info.get('constraints') or object_type == "TABLE":
                 st.subheader("Constraints" + (" (Info)" if object_type == "VIEW" else ""))
                 display_constraints(object_info.get('constraints'))


if __name__ == "__main__":
    main() 