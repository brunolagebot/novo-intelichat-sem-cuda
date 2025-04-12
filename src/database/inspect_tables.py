import sqlite3
import os
from dotenv import load_dotenv
from tabulate import tabulate
import sys

def load_database_path():
    """Carrega o caminho do banco de dados do arquivo .env"""
    load_dotenv()
    return os.getenv('DB_PATH', 'chat_history.db')

def get_tables(cursor):
    """Retorna a lista de todas as tabelas no banco de dados"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [table[0] for table in cursor.fetchall()]

def get_table_schema(cursor, table_name):
    """Retorna o schema de uma tabela específica"""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return cursor.fetchall()

def preview_table_data(cursor, table_name, limit=5):
    """Retorna uma prévia dos dados de uma tabela"""
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        rows = cursor.fetchall()
        # Obtém os nomes das colunas
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        return columns, rows
    except sqlite3.Error as e:
        print(f"Erro ao acessar a tabela {table_name}: {e}")
        return None, None

def main():
    """Função principal para inspecionar o banco de dados"""
    db_path = load_database_path()
    
    if not os.path.exists(db_path):
        print(f"ERRO: Banco de dados não encontrado em {db_path}")
        sys.exit(1)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Lista todas as tabelas
        tables = get_tables(cursor)
        print("\n=== Tabelas Disponíveis ===")
        for i, table in enumerate(tables, 1):
            print(f"{i}. {table}")
        
        while True:
            print("\nOpções:")
            print("1. Ver schema de uma tabela")
            print("2. Ver prévia dos dados de uma tabela")
            print("3. Sair")
            
            choice = input("\nEscolha uma opção (1-3): ")
            
            if choice == "3":
                break
            
            if choice in ["1", "2"]:
                print("\nTabelas disponíveis:")
                for i, table in enumerate(tables, 1):
                    print(f"{i}. {table}")
                
                table_idx = int(input("\nEscolha o número da tabela: ")) - 1
                if 0 <= table_idx < len(tables):
                    table_name = tables[table_idx]
                    
                    if choice == "1":
                        # Mostra o schema
                        schema = get_table_schema(cursor, table_name)
                        print(f"\n=== Schema da Tabela {table_name} ===")
                        headers = ["ID", "Nome", "Tipo", "NotNull", "Default", "PK"]
                        print(tabulate(schema, headers=headers, tablefmt="grid"))
                    
                    else:  # choice == "2"
                        # Mostra prévia dos dados
                        limit = int(input("Quantas linhas deseja visualizar? (padrão: 5) ") or 5)
                        columns, rows = preview_table_data(cursor, table_name, limit)
                        if columns and rows:
                            print(f"\n=== Prévia dos Dados da Tabela {table_name} ===")
                            print(tabulate(rows, headers=columns, tablefmt="grid"))
                else:
                    print("Número de tabela inválido!")
            else:
                print("Opção inválida!")
        
        conn.close()
        print("\nInspeção concluída!")
        
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 