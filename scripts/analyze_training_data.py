"""
Script para análise dos dados de treinamento.
Este script analisa o dataset gerado para fine-tuning, fornecendo métricas e visualizações
úteis para entender a qualidade e características dos dados antes do treinamento.
"""

import json
import os
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from typing import Dict, List, Tuple
import seaborn as sns
from tabulate import tabulate
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_dataset(file_path: str) -> List[Dict]:
    """Carrega o dataset de treinamento."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset não encontrado: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def analyze_message_lengths(data: List[Dict]) -> Tuple[pd.Series, pd.Series]:
    """Analisa o comprimento das mensagens no dataset."""
    user_lengths = []
    assistant_lengths = []
    
    for item in data:
        for msg in item['messages']:
            length = len(msg['content'].split())
            if msg['role'] == 'user':
                user_lengths.append(length)
            else:
                assistant_lengths.append(length)
    
    return pd.Series(user_lengths), pd.Series(assistant_lengths)

def analyze_conversation_structure(data: List[Dict]) -> Dict:
    """Analisa a estrutura das conversas no dataset."""
    conversation_lengths = []
    role_patterns = []
    
    for item in data:
        messages = item['messages']
        conversation_lengths.append(len(messages))
        pattern = '-'.join([msg['role'][:1].upper() for msg in messages])
        role_patterns.append(pattern)
    
    return {
        'conversation_lengths': pd.Series(conversation_lengths),
        'role_patterns': Counter(role_patterns)
    }

def plot_length_distributions(
    user_lengths: pd.Series,
    assistant_lengths: pd.Series,
    output_dir: str
):
    """Plota distribuições de comprimento das mensagens."""
    plt.figure(figsize=(12, 6))
    
    plt.subplot(1, 2, 1)
    sns.histplot(user_lengths, bins=30)
    plt.title('Distribuição do Comprimento das Mensagens do Usuário')
    plt.xlabel('Número de Palavras')
    plt.ylabel('Frequência')
    
    plt.subplot(1, 2, 2)
    sns.histplot(assistant_lengths, bins=30)
    plt.title('Distribuição do Comprimento das Mensagens do Assistente')
    plt.xlabel('Número de Palavras')
    plt.ylabel('Frequência')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'message_length_distributions.png'))
    plt.close()

def plot_conversation_structure(
    conversation_data: Dict,
    output_dir: str
):
    """Plota análises da estrutura das conversas."""
    plt.figure(figsize=(12, 6))
    
    plt.subplot(1, 2, 1)
    sns.histplot(conversation_data['conversation_lengths'], bins=20)
    plt.title('Distribuição do Comprimento das Conversas')
    plt.xlabel('Número de Mensagens')
    plt.ylabel('Frequência')
    
    plt.subplot(1, 2, 2)
    patterns = list(conversation_data['role_patterns'].keys())
    counts = list(conversation_data['role_patterns'].values())
    plt.bar(patterns, counts)
    plt.title('Padrões de Papéis nas Conversas')
    plt.xlabel('Padrão (U=Usuário, A=Assistente)')
    plt.ylabel('Frequência')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'conversation_structure.png'))
    plt.close()

def generate_summary_report(
    data: List[Dict],
    user_lengths: pd.Series,
    assistant_lengths: pd.Series,
    conversation_data: Dict,
    output_dir: str
):
    """Gera um relatório resumido da análise."""
    report = [
        ["Métrica", "Valor"],
        ["Total de Exemplos", len(data)],
        ["Média de Palavras (Usuário)", f"{user_lengths.mean():.2f}"],
        ["Média de Palavras (Assistente)", f"{assistant_lengths.mean():.2f}"],
        ["Média de Mensagens por Conversa", f"{conversation_data['conversation_lengths'].mean():.2f}"],
        ["Padrão de Conversa Mais Comum", max(conversation_data['role_patterns'].items(), key=lambda x: x[1])[0]]
    ]
    
    report_path = os.path.join(output_dir, 'analysis_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(tabulate(report, headers='firstrow', tablefmt='grid'))
        f.write("\n\nPadrões de Conversa Detalhados:\n")
        for pattern, count in conversation_data['role_patterns'].items():
            f.write(f"{pattern}: {count} ocorrências\n")

def main():
    """Função principal para executar a análise."""
    # Configurações
    dataset_file = "table_training_data.json"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./analysis_results_{timestamp}"
    
    try:
        # Cria diretório de saída
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info("Iniciando análise dos dados de treinamento")
        logger.info(f"Dataset: {dataset_file}")
        logger.info(f"Diretório de saída: {output_dir}")
        
        # Carrega dados
        logger.info("Carregando dataset...")
        data = load_dataset(dataset_file)
        
        # Análise de comprimento das mensagens
        logger.info("Analisando comprimento das mensagens...")
        user_lengths, assistant_lengths = analyze_message_lengths(data)
        
        # Análise da estrutura das conversas
        logger.info("Analisando estrutura das conversas...")
        conversation_data = analyze_conversation_structure(data)
        
        # Gera visualizações
        logger.info("Gerando visualizações...")
        plot_length_distributions(user_lengths, assistant_lengths, output_dir)
        plot_conversation_structure(conversation_data, output_dir)
        
        # Gera relatório
        logger.info("Gerando relatório resumido...")
        generate_summary_report(
            data,
            user_lengths,
            assistant_lengths,
            conversation_data,
            output_dir
        )
        
        logger.info(f"Análise concluída! Resultados salvos em: {output_dir}")
        
    except Exception as e:
        logger.error(f"Erro durante a análise: {str(e)}")
        raise

if __name__ == "__main__":
    main() 