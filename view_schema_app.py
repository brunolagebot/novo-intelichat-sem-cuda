import streamlit as st
import json
import pandas as pd
import fdb
import logging

# Configuração do Logging (opcional para Streamlit, mas útil para depuração)
# Nível DEBUG para ver dados brutos da amostra
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

SCHEMA_FILE = "firebird_schema.json"

# --- Configurações Padrão --- (Podem ser sobrescritas na interface)
DEFAULT_DB_PATH = r"C:\Projetos\DADOS.FDB"
DEFAULT_DB_USER = "SYSDBA"
DEFAULT_DB_CHARSET = "WIN1252"
DEFAULT_SAMPLE_SIZE = 10

# --- Inicialização do Estado da Sessão --- (Para armazenar a senha temporariamente)
if 'db_password' not in st.session_state:
    st.session_state.db_password = ""

@st.cache_data # Cache para evitar recarregar o JSON a cada interação
def load_schema(file_path):
    """Carrega o esquema do banco de dados do arquivo JSON."""
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

def main():
    st.set_page_config(page_title="Visualizador de Esquema Firebird", layout="wide")
    st.title("🔎 Visualizador de Esquema Firebird")
    st.markdown(f"Carregando esquema do arquivo: `{SCHEMA_FILE}`")
    schema_data = load_schema(SCHEMA_FILE)
    if not schema_data:
        return

    # --- Barra Lateral para Configurações de Conexão (se necessário) ---
    st.sidebar.header("Configurações de Conexão (para Amostra)")
    db_path_input = st.sidebar.text_input("Caminho do Banco (.fdb)", value=DEFAULT_DB_PATH)
    db_user_input = st.sidebar.text_input("Usuário do Banco", value=DEFAULT_DB_USER)
    db_charset_input = st.sidebar.text_input("Charset", value=DEFAULT_DB_CHARSET)
    sample_size_input = st.sidebar.number_input("Tamanho da Amostra", min_value=1, max_value=100, value=DEFAULT_SAMPLE_SIZE)

    # --- Conteúdo Principal ---
    object_names = sorted(list(schema_data.keys()))

    if not object_names:
        st.warning("Nenhum objeto (tabela/view) encontrado no arquivo de esquema.")
        return

    selected_object = st.selectbox("Selecione uma Tabela ou View:", object_names)

    if selected_object:
        object_info = schema_data[selected_object]
        object_type = object_info.get("object_type", "DESCONHECIDO") # Pega o tipo do schema

        st.header(f"Esquema: `{selected_object}` ({object_type})") # Mostra o tipo

        # Exibir Colunas
        st.subheader("Colunas")
        if object_info.get('columns'):
            df_columns = pd.DataFrame(object_info['columns'])
            df_columns.rename(columns={'name': 'Nome', 'type': 'Tipo', 'nullable': 'Permite Nulo'}, inplace=True)
            st.dataframe(df_columns[['Nome', 'Tipo', 'Permite Nulo']], use_container_width=True)
        else:
            st.write("Nenhuma coluna definida para este objeto.")

        # Exibir Constraints
        st.divider()
        # Só mostra seção de constraints se houver alguma ou for tabela
        if object_info.get('constraints') or object_type == "TABLE":
            st.subheader("Constraints" + (" (geralmente vazio para Views)" if object_type == "VIEW" else ""))
            display_constraints(object_info.get('constraints'))

        # --- Seção para Amostra de Dados ---
        st.divider()
        st.header("Amostra de Dados")

        # Usar um expander para não poluir a interface inicialmente
        with st.expander(f"Mostrar as primeiras {sample_size_input} linhas de `{selected_object}`?"):
            st.warning("Isso conectará diretamente ao banco de dados.")

            # Input para a senha. Não definimos 'value' para não preencher automaticamente
            # se a senha já estiver na session_state.
            # A lógica do botão cuidará de usar a senha da session_state se disponível.
            db_password_input_value = st.text_input(
                f"Senha para o usuário '{db_user_input}': (será armazenada na sessão)",
                type="password",
                key=f"pwd_{selected_object}"
            )

            if st.button(f"Buscar Amostra de '{selected_object}'", key=f"btn_{selected_object}"):
                # 1. Atualiza a senha na session_state se o usuário digitou algo
                if db_password_input_value:
                    st.session_state.db_password = db_password_input_value
                    logger.info("Senha atualizada na session_state a partir do input.")

                # 2. Verifica se temos uma senha (seja do input atual ou da session_state)
                if not st.session_state.db_password:
                    st.error("Por favor, digite a senha.")
                    # Usar st.stop() para evitar a tentativa de busca sem senha
                    st.stop()
                else:
                    # 3. Procede com a busca usando a senha da session_state
                    with st.spinner("Buscando dados..."):
                        sample_df = fetch_sample_data(
                            db_path=db_path_input,
                            user=db_user_input,
                            password=st.session_state.db_password, # Usa a senha da session_state
                            charset=db_charset_input,
                            table_name=selected_object,
                            sample_size=sample_size_input
                        )

                    if sample_df is not None:
                        if not sample_df.empty:
                            st.dataframe(sample_df, use_container_width=True)
                        else:
                            # Verifica se retornou colunas, indicando que a query rodou mas não achou linhas
                            if list(sample_df.columns):
                                st.info(f"A consulta para '{selected_object}' retornou 0 linhas.")
                            else: # Se nem colunas retornou, provavelmente erro antes
                                st.warning(f"Não foi possível buscar dados para '{selected_object}'. Verifique os logs ou a conexão.")
                        # Mensagens de erro já são tratadas dentro de fetch_sample_data

if __name__ == "__main__":
    main() 