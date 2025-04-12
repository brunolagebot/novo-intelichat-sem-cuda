import sqlite3
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import sys

def load_database_path():
    """Carrega o caminho do banco de dados do arquivo .env"""
    load_dotenv()
    return os.getenv('DB_PATH', 'chat_history.db')

def get_table_schema(cursor, table_name: str) -> List[Dict[str, Any]]:
    """Retorna o schema detalhado de uma tabela"""
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    schema = []
    for col in columns:
        col_id, name, type_, notnull, default, pk = col
        schema.append({
            "name": name,
            "type": type_,
            "required": bool(notnull),
            "primary_key": bool(pk),
            "default": default
        })
    return schema

def get_table_relationships(cursor, table_name: str) -> List[Dict[str, str]]:
    """Retorna as relações (chaves estrangeiras) de uma tabela"""
    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
    relations = cursor.fetchall()
    
    relationships = []
    for rel in relations:
        relationships.append({
            "table": rel[2],  # tabela referenciada
            "from": rel[3],   # coluna local
            "to": rel[4]      # coluna referenciada
        })
    return relationships

def generate_schema_description(table_name: str, schema: List[Dict[str, Any]], relationships: List[Dict[str, str]]) -> str:
    """Gera uma descrição em linguagem natural do schema da tabela"""
    description = f"A tabela '{table_name}' possui os seguintes campos:\n\n"
    
    # Descreve cada coluna
    for col in schema:
        pk_text = " (Chave Primária)" if col["primary_key"] else ""
        required_text = " (Obrigatório)" if col["required"] else " (Opcional)"
        default_text = f" (Valor padrão: {col['default']})" if col["default"] else ""
        
        description += f"- {col['name']}: {col['type']}{pk_text}{required_text}{default_text}\n"
    
    # Descreve relacionamentos
    if relationships:
        description += "\nRelacionamentos:\n"
        for rel in relationships:
            description += f"- Campo '{rel['from']}' referencia '{rel['to']}' na tabela '{rel['table']}'\n"
    
    return description

def generate_training_examples(cursor, table_name: str, schema: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, str]]:
    """Gera exemplos de treinamento baseados nos dados reais da tabela"""
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
    rows = cursor.fetchall()
    
    # Obtém nomes das colunas
    column_names = [col["name"] for col in schema]
    
    examples = []
    for row in rows:
        # Cria um dicionário com os dados da linha
        data = dict(zip(column_names, row))
        
        # Gera uma pergunta sobre os dados
        question = f"Quais são os valores dos campos da tabela {table_name} para o registro com {schema[0]['name']} = {row[0]}?"
        
        # Gera uma resposta descritiva
        answer = f"Para o registro com {schema[0]['name']} = {row[0]} na tabela {table_name}, os valores são:\n"
        for col, val in data.items():
            answer += f"- {col}: {val}\n"
        
        examples.append({
            "question": question,
            "answer": answer
        })
    
    return examples

def save_training_data(data: Dict[str, Any], output_file: str):
    """Salva os dados de treinamento em um arquivo JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    """Função principal para preparar os dados de treinamento"""
    db_path = load_database_path()
    
    if not os.path.exists(db_path):
        print(f"ERRO: Banco de dados não encontrado em {db_path}")
        sys.exit(1)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Lista todas as tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        
        print("\n=== Tabelas Disponíveis ===")
        for i, table in enumerate(tables, 1):
            print(f"{i}. {table}")
        
        # Permite seleção múltipla de tabelas
        selected_indices = input("\nEscolha os números das tabelas (separados por vírgula): ").split(',')
        selected_tables = []
        
        for idx in selected_indices:
            try:
                table_idx = int(idx.strip()) - 1
                if 0 <= table_idx < len(tables):
                    selected_tables.append(tables[table_idx])
            except ValueError:
                continue
        
        if not selected_tables:
            print("Nenhuma tabela válida selecionada!")
            sys.exit(1)
        
        training_data = {
            "schema_descriptions": [],
            "training_examples": []
        }
        
        # Processa cada tabela selecionada
        for table_name in selected_tables:
            print(f"\nProcessando tabela: {table_name}")
            
            # Obtém schema e relacionamentos
            schema = get_table_schema(cursor, table_name)
            relationships = get_table_relationships(cursor, table_name)
            
            # Gera descrição do schema
            description = generate_schema_description(table_name, schema, relationships)
            training_data["schema_descriptions"].append({
                "table": table_name,
                "description": description
            })
            
            # Gera exemplos de treinamento
            examples = generate_training_examples(cursor, table_name, schema)
            training_data["training_examples"].extend(examples)
        
        # Salva os dados de treinamento
        output_file = "table_training_data.json"
        save_training_data(training_data, output_file)
        
        print(f"\nDados de treinamento salvos em: {output_file}")
        print(f"Total de exemplos gerados: {len(training_data['training_examples'])}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 