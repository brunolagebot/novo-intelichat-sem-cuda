# Análise de Dados de Treinamento

Este projeto contém scripts para analisar dados de treinamento usados para fine-tuning de modelos de linguagem. O objetivo é fornecer métricas e visualizações para entender a qualidade e características dos dados antes do treinamento.

## Funcionalidades

- Análise de comprimento de mensagens (usuário e assistente)
- Análise da estrutura das conversas
- Visualizações de distribuições
- Geração de relatório resumido

## Requisitos

*   Python 3.8+ (recomendado 3.10 ou superior)
*   Dependências listadas no arquivo `requirements.txt`.
*   Ollama instalado (opcional, para executar a interface de chat localmente). Veja [Ollama](https://ollama.com/).

## Instalação

1. Clone o repositório
2. Crie um ambiente virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

1. Coloque seus dados de treinamento em um arquivo JSON no formato esperado
2. Execute o script de análise:
```bash
python analyze_training_data.py
```

3. Os resultados serão salvos em uma pasta `output_[timestamp]` contendo:
- `message_length_distributions.png`: Gráfico de distribuição de comprimentos
- `conversation_structure.png`: Gráfico da estrutura das conversas
- `analysis_report.txt`: Relatório detalhado da análise

## Estrutura do Projeto

```
.
├── analyze_training_data.py   # Script principal de análise
├── requirements.txt           # Dependências do projeto
└── README.md                 # Esta documentação
```

## Contribuindo

Sinta-se à vontade para abrir issues ou enviar pull requests com melhorias.

## Licença

MIT 