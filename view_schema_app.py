import streamlit as st
import json
import pandas as pd

SCHEMA_FILE = "firebird_schema.json"

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

def main():
    st.set_page_config(page_title="Visualizador de Esquema Firebird", layout="wide")
    st.title("🔎 Visualizador de Esquema Firebird")
    st.markdown(f"Carregando esquema do arquivo: `{SCHEMA_FILE}`")

    schema_data = load_schema(SCHEMA_FILE)

    if schema_data:
        table_names = sorted(list(schema_data.keys()))

        if not table_names:
            st.warning("Nenhuma tabela encontrada no arquivo de esquema.")
            return

        selected_table = st.selectbox("Selecione uma Tabela:", table_names)

        if selected_table:
            st.header(f"Esquema da Tabela: `{selected_table}`")
            table_info = schema_data[selected_table]

            # Exibir Colunas
            st.subheader("Colunas")
            if table_info.get('columns'):
                # Criar DataFrame para melhor visualização
                df_columns = pd.DataFrame(table_info['columns'])
                df_columns.rename(columns={'name': 'Nome', 'type': 'Tipo', 'nullable': 'Permite Nulo'}, inplace=True)
                st.dataframe(df_columns[['Nome', 'Tipo', 'Permite Nulo']], use_container_width=True)
            else:
                st.write("Nenhuma coluna definida para esta tabela.")

            # Exibir Constraints
            st.divider()
            display_constraints(table_info.get('constraints'))

if __name__ == "__main__":
    main() 