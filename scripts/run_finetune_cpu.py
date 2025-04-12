"""
Script para realizar fine-tuning do modelo em CPUs.
Este script é otimizado para treinar em computadores sem GPU, usando técnicas específicas
para melhorar a performance em CPU e reduzir o uso de memória.
"""

import os
import json
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
from datasets import load_dataset
import logging
from datetime import datetime
from typing import Dict, List

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_and_process_data(dataset_file: str) -> List[Dict]:
    """Carrega e processa o dataset de treinamento."""
    if not os.path.exists(dataset_file):
        raise FileNotFoundError(f"Dataset não encontrado: {dataset_file}")
    
    with open(dataset_file, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]
    
    # Formata os dados para o formato esperado pelo modelo
    formatted_data = []
    for item in data:
        messages = item['messages']
        conversation = ""
        for msg in messages:
            role_prefix = "Human: " if msg['role'] == 'user' else "Assistant: "
            conversation += role_prefix + msg['content'] + "\n"
        formatted_data.append({"text": conversation})
    
    return formatted_data

def create_cpu_optimized_config(
    base_model_name: str,
    output_dir: str,
    dataset_file: str
) -> TrainingArguments:
    """Cria configuração otimizada para treinar em CPU."""
    return TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=1,
        per_device_train_batch_size=1,  # Batch size menor para CPU
        gradient_accumulation_steps=8,   # Acumula gradientes para compensar batch size menor
        warmup_steps=2,
        logging_steps=1,
        save_steps=20,
        learning_rate=2e-4,
        fp16=False,  # Desabilita precisão mista que requer GPU
        bf16=False,  # Desabilita precisão mista que requer GPU
        optim="adamw_torch",  # Otimizador padrão do PyTorch
        logging_dir=f"{output_dir}/logs",
        group_by_length=True,  # Agrupa sequências de tamanho similar
        report_to="none",  # Desabilita relatórios para Wandb/Tensorboard
        save_total_limit=2,  # Mantém apenas os 2 últimos checkpoints
    )

def create_lora_config() -> LoraConfig:
    """Cria configuração LoRA otimizada para CPU."""
    return LoraConfig(
        r=8,  # Rank menor para reduzir memória
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM
    )

def main():
    """Função principal para executar o fine-tuning."""
    # Configurações
    base_model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
    dataset_file = "table_training_data.json"  # Arquivo gerado pelo prepare_training_data.py
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"./results-llama3-8b-chat-cpu-adapter-{timestamp}"
    
    logger.info("Iniciando processo de fine-tuning em CPU")
    logger.info(f"Modelo base: {base_model_name}")
    logger.info(f"Dataset: {dataset_file}")
    logger.info(f"Diretório de saída: {output_dir}")
    
    try:
        # Carrega e processa os dados
        logger.info("Carregando dados de treinamento...")
        training_data = load_and_process_data(dataset_file)
        
        # Carrega o modelo e tokenizer
        logger.info("Carregando modelo e tokenizer...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            device_map="cpu",
            torch_dtype=torch.float32,  # Usa precisão padrão para CPU
            use_cache=False  # Desabilita KV cache para economizar memória
        )
        tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        
        # Prepara o modelo para treinamento
        logger.info("Preparando modelo para treinamento...")
        model = prepare_model_for_kbit_training(model)
        
        # Aplica configuração LoRA
        logger.info("Aplicando configuração LoRA...")
        lora_config = create_lora_config()
        model = get_peft_model(model, lora_config)
        
        # Cria dataset no formato HuggingFace
        logger.info("Preparando dataset...")
        dataset = load_dataset("json", data_files={"train": dataset_file})
        
        # Configura o treinamento
        logger.info("Configurando parâmetros de treinamento...")
        training_args = create_cpu_optimized_config(
            base_model_name=base_model_name,
            output_dir=output_dir,
            dataset_file=dataset_file
        )
        
        # Inicia o treinamento
        logger.info("Iniciando treinamento...")
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
        )
        
        trainer.train()
        
        # Salva o modelo e configurações
        logger.info(f"Salvando modelo em {output_dir}...")
        trainer.save_model()
        
        logger.info("Treinamento concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante o treinamento: {str(e)}")
        raise

if __name__ == "__main__":
    main() 