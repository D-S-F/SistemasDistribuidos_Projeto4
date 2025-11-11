from flask import Flask, jsonify, request
import pika
import json
import datetime
import time
import threading
import utils
from typing import Dict

app = Flask(__name__)

# Armazenamento em memória dos leilões
leiloes: Dict[str, Dict] = {}

class CicloVidaLeilao(threading.Thread):
    """Thread que monitora o ciclo de vida dos leilões"""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.connection = None
        self.channel = None

    def connect(self):
        """Conecta ao RabbitMQ"""
        self.connection = utils.get_rabbitmq_connection()
        self.channel = self.connection.channel()
        utils.setup_queues(self.channel)

    def disconnect(self):
        """Desconecta do RabbitMQ"""
        if self.connection and self.connection.is_open:
            self.connection.close()

    def publicar_leilao_iniciado(self, leilao_id: str, leilao: Dict):
        """Publica evento de leilão iniciado"""
        evento = {
            "leilao_id": leilao_id,
            "desc": leilao.get("desc", ""),
            "valor_inicial": leilao.get("valor_inicial", 0),
            "inicio": leilao.get("inicio", ""),
            "fim": leilao.get("fim", "")
        }
        self.channel.basic_publish(
            exchange='',
            routing_key='leilao_iniciado',
            body=json.dumps(evento),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistente
        )
        print(f"[MS Leilão] ✅ Leilão {leilao_id} iniciado: {leilao.get('desc')}")

    def publicar_leilao_finalizado(self, leilao_id: str, leilao: Dict):
        """Publica evento de leilão finalizado"""
        evento = {
            "leilao_id": leilao_id,
            "desc": leilao.get("desc", ""),
            "fim": leilao.get("fim", "")
        }
        self.channel.basic_publish(
            exchange='',
            routing_key='leilao_finalizado',
            body=json.dumps(evento),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistente
        )
        print(f"[MS Leilão] 🏁 Leilão {leilao_id} finalizado: {leilao.get('desc')}")

    def verificar_ciclo_vida(self):
        """Verifica e atualiza o ciclo de vida dos leilões"""
        agora = datetime.datetime.now()

        for leilao_id, leilao in leiloes.items():
            status = leilao.get("status", "agendado")
            inicio_str = leilao.get("inicio", "")
            fim_str = leilao.get("fim", "")

            try:
                inicio = datetime.datetime.fromisoformat(inicio_str.replace('Z', '+00:00'))
                fim = datetime.datetime.fromisoformat(fim_str.replace('Z', '+00:00'))
                
                # Remove timezone para comparação
                if inicio.tzinfo:
                    inicio = inicio.replace(tzinfo=None)
                if fim.tzinfo:
                    fim = fim.replace(tzinfo=None)

                # Verifica se deve iniciar
                if status == "agendado" and agora >= inicio and agora < fim:
                    leilao["status"] = "ativo"
                    self.publicar_leilao_iniciado(leilao_id, leilao)

                # Verifica se deve finalizar
                elif status == "ativo" and agora >= fim:
                    leilao["status"] = "finalizado"
                    self.publicar_leilao_finalizado(leilao_id, leilao)

            except (ValueError, AttributeError) as e:
                print(f"[MS Leilão] Erro ao processar datas do leilão {leilao_id}: {e}")

    def run(self):
        """Loop principal de monitoramento"""
        try:
            self.connect()
            while self.running:
                self.verificar_ciclo_vida()
                time.sleep(5)  # Verifica a cada 5 segundos
        except Exception as e:
            print(f"[MS Leilão] Erro no monitoramento: {e}")
        finally:
            self.disconnect()

# Inicia thread de monitoramento
monitor_thread = CicloVidaLeilao()
monitor_thread.start()

# --- Endpoints REST ---

@app.route('/leiloes', methods=['POST'])
def criar_leilao():
    """Cria um novo leilão"""
    dados = request.get_json()
    
    if not dados:
        return jsonify({"erro": "Dados não fornecidos"}), 400

    # Validação dos campos obrigatórios
    campos_obrigatorios = ['id', 'desc', 'hora_finalizacao', 'criador_id']
    for campo in campos_obrigatorios:
        if campo not in dados:
            return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

    leilao_id = str(dados['id'])
    
    # Verifica se o leilão já existe
    if leilao_id in leiloes:
        return jsonify({"erro": f"Leilão com ID {leilao_id} já existe"}), 409

    # Processa a data/hora de finalização
    try:
        hora_fim = datetime.datetime.fromisoformat(dados['hora_finalizacao'].replace('Z', '+00:00'))
        if hora_fim.tzinfo:
            hora_fim = hora_fim.replace(tzinfo=None)
        
        # Define início como agora e fim como a hora fornecida
        hora_inicio = datetime.datetime.now()
        
        # Se a hora de finalização já passou, retorna erro
        if hora_fim <= hora_inicio:
            return jsonify({"erro": "A data/hora de finalização deve ser futura"}), 400

    except (ValueError, AttributeError) as e:
        return jsonify({"erro": f"Formato de data inválido: {e}"}), 400

    # Cria o leilão
    novo_leilao = {
        "id": leilao_id,
        "desc": dados['desc'],
        "valor_inicial": dados.get('valor_inicial', 0),
        "criador_id": dados['criador_id'],
        "inicio": hora_inicio.isoformat(),
        "fim": hora_fim.isoformat(),
        "status": "agendado"
    }

    leiloes[leilao_id] = novo_leilao

    # Verifica imediatamente se deve iniciar (sem esperar o ciclo de vida)
    agora = datetime.datetime.now()
    if hora_inicio <= agora < hora_fim:
        novo_leilao["status"] = "ativo"
        # Garante que o monitor_thread está conectado
        if not monitor_thread.channel or not monitor_thread.channel.is_open:
            monitor_thread.connect()
        # Publica evento de início imediatamente
        monitor_thread.publicar_leilao_iniciado(leilao_id, novo_leilao)
        print(f"[MS Leilão] ✅ Leilão criado e iniciado imediatamente: {leilao_id} - {dados['desc']}")
    else:
        print(f"[MS Leilão] ✅ Leilão criado (agendado): {leilao_id} - {dados['desc']}")
    
    return jsonify(novo_leilao), 201

@app.route('/leiloes', methods=['GET'])
def consultar_leiloes():
    """Consulta leilões ativos"""
    # Filtra apenas leilões ativos
    leiloes_ativos = []
    agora = datetime.datetime.now()

    for leilao_id, leilao in leiloes.items():
        status = leilao.get("status", "agendado")
        
        # Considera ativo se status é "ativo" ou se está entre início e fim
        try:
            inicio = datetime.datetime.fromisoformat(leilao.get("inicio", "").replace('Z', '+00:00'))
            fim = datetime.datetime.fromisoformat(leilao.get("fim", "").replace('Z', '+00:00'))
            
            if inicio.tzinfo:
                inicio = inicio.replace(tzinfo=None)
            if fim.tzinfo:
                fim = fim.replace(tzinfo=None)

            if status == "ativo" or (inicio <= agora < fim):
                # Retorna dados formatados para o frontend
                leilao_info = {
                    "id": leilao_id,
                    "desc": leilao.get("desc", ""),
                    "valor_inicial": leilao.get("valor_inicial", 0),
                    "inicio": leilao.get("inicio", ""),
                    "fim": leilao.get("fim", ""),
                    "status": "ativo"
                }
                leiloes_ativos.append(leilao_info)
        except (ValueError, AttributeError):
            continue

    return jsonify(leiloes_ativos), 200

if __name__ == '__main__':
    print("🚀 MS Leilão iniciado na porta 4999")
    print("📡 Monitorando ciclo de vida dos leilões...")
    # use_reloader=False evita que o Flask reinicie e perca o estado das threads
    app.run(debug=True, port=4999, threaded=True, use_reloader=False)

