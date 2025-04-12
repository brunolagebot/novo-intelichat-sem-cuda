import time
import psutil
import logging
from typing import List, Dict, Tuple, Optional
from src.ollama_integration.client import chat_completion, get_available_models

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MonitoredChat:
    """Gerencia uma sessão de chat interativa com monitoramento de desempenho."""

    def __init__(self, model: Optional[str] = None):
        self.history: List[Dict[str, str]] = []
        self.model = model or self._get_default_model()
        self.performance_data: List[Dict[str, float]] = []
        logging.info(f"Iniciando chat com o modelo: {self.model}")

    def _get_default_model(self) -> str:
        """Obtém o modelo padrão, priorizando a lista da API se disponível."""
        available_models = get_available_models()
        if available_models:
            # Poderíamos adicionar lógica para escolher o melhor modelo leve
            # Por enquanto, vamos usar o primeiro da lista ou 'orca-mini' se a lista estiver vazia
            # (Embora get_available_models já retorne um fallback)
            return available_models[0]
        return "orca-mini" # Fallback final

    def _monitor_performance(self, start_time: float, end_time: float) -> Dict[str, float]:
        """Monitora e retorna o uso de CPU, memória e o tempo de resposta."""
        process = psutil.Process()
        cpu_usage = process.cpu_percent(interval=0.1) # Pequeno intervalo para medição
        memory_info = process.memory_info()
        memory_usage_mb = memory_info.rss / (1024 * 1024) # RSS em MB
        response_time = end_time - start_time
        
        stats = {
            "response_time_seconds": round(response_time, 3),
            "cpu_percent": cpu_usage,
            "memory_rss_mb": round(memory_usage_mb, 2)
        }
        self.performance_data.append(stats)
        logging.info(f"Desempenho da última chamada: {stats}")
        return stats

    def send_message(self, user_input: str) -> Optional[str]:
        """Envia a mensagem do usuário, obtém a resposta e monitora o desempenho."""
        if not user_input or user_input.strip().lower() in ["sair", "exit", "quit"]:
            return None

        self.history.append({"role": "user", "content": user_input})
        logging.debug(f"Histórico antes da chamada: {self.history}")

        start_time = time.time()
        response_content = chat_completion(messages=self.history, model=self.model, stream=False)
        end_time = time.time()

        if response_content:
            self.history.append({"role": "assistant", "content": response_content})
            self._monitor_performance(start_time, end_time)
            logging.debug(f"Histórico após a chamada: {self.history}")
            return response_content
        else:
            logging.error("Falha ao obter resposta do modelo.")
            # Remove a última mensagem do usuário do histórico se a API falhou
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return "Desculpe, não consegui processar sua solicitação."

    def get_performance_summary(self) -> Dict[str, float]:
        """Calcula estatísticas agregadas do desempenho da sessão."""
        if not self.performance_data:
            return {"avg_response_time": 0, "max_cpu": 0, "max_memory_mb": 0}

        total_time = sum(p["response_time_seconds"] for p in self.performance_data)
        max_cpu = max(p["cpu_percent"] for p in self.performance_data)
        max_mem = max(p["memory_rss_mb"] for p in self.performance_data)
        avg_time = total_time / len(self.performance_data)

        return {
            "avg_response_time_seconds": round(avg_time, 3),
            "max_cpu_percent": max_cpu,
            "max_memory_rss_mb": round(max_mem, 2)
        }

    def run_interactive_chat(self):
        """Inicia o loop de chat interativo no console."""
        print(f"Chat iniciado com o modelo '{self.model}'. Digite 'sair' para terminar.")
        while True:
            try:
                user_input = input("Você: ")
                if user_input.strip().lower() in ["sair", "exit", "quit"]:
                    print("Encerrando o chat...")
                    break
                
                response = self.send_message(user_input)
                if response:
                    print(f"Modelo ({self.model}): {response}")
                else:
                    # send_message já loga o erro, aqui podemos só informar o usuário
                    print("Ocorreu um erro ao processar sua mensagem.")

            except KeyboardInterrupt:
                print("\nEncerrando o chat...")
                break
            except Exception as e:
                logging.exception("Erro inesperado no loop do chat:")
                print(f"Ocorreu um erro inesperado: {e}")
                break # Sai do loop em caso de erro grave
        
        # Exibe resumo do desempenho no final
        summary = self.get_performance_summary()
        print("\n--- Resumo do Desempenho da Sessão ---")
        print(f"Tempo médio de resposta: {summary['avg_response_time_seconds']}s")
        print(f"Pico de uso de CPU: {summary['max_cpu_percent']}%")
        print(f"Pico de uso de memória (RSS): {summary['max_memory_rss_mb']}MB")
        print("-------------------------------------")

# Exemplo de como usar (pode ser movido para main.py ou outro script)
if __name__ == '__main__':
    chat_session = MonitoredChat()
    chat_session.run_interactive_chat() 