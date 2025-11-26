from flask import Flask, jsonify, request
import pika
import json
import threading
import utils
from typing import Dict, Set

app = Flask(__name__)

# Armazenamento em memória
leiloes_ativos: Set[str] = set()  # IDs de leilões ativos
maiores_lances: Dict[str, Dict] = {}  # {leilao_id: {"usuario_id": str, "valor": float}}
lock_leiloes = threading.Lock()  # Lock para sincronização

class ConsumidorEventos(threading.Thread):
    """Thread que consome eventos do RabbitMQ"""
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

    def processar_leilao_iniciado(self, ch, method, properties, body):
        """Processa evento de leilão iniciado"""
        try:
            evento = json.loads(body.decode('utf-8'))
            leilao_id = str(evento.get('id'))  # Garante que é string
            
            if leilao_id:
                with lock_leiloes:
                    leiloes_ativos.add(leilao_id)
                    maiores_lances[leilao_id] = {"usuario_id": None, "valor": 0}
                print(f"[MS Lance] ✅ Leilão {leilao_id} está ativo")
                with lock_leiloes:
                    print(f"[MS Lance] Debug: leiloes_ativos = {leiloes_ativos}")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[MS Lance] Erro ao processar leilao_iniciado: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def processar_leilao_finalizado(self, ch, method, properties, body):
        """Processa evento de leilão finalizado"""
        try:
            evento = json.loads(body.decode('utf-8'))
            leilao_id = str(evento.get('id'))  # Garante que é string
            
            with lock_leiloes:
                if leilao_id in leiloes_ativos:
                    leiloes_ativos.remove(leilao_id)
                    
                    # Determina o vencedor
                    vencedor = maiores_lances.get(leilao_id)
                    
                    if vencedor and vencedor.get("usuario_id"):
                        # Publica evento leilao_vencedor
                        evento_vencedor = {
                            "id": leilao_id,
                            "vencedor_id": vencedor["usuario_id"],
                            "valor": vencedor["valor"]
                        }
                        
                        self.channel.basic_publish(
                            exchange='leilao_vencedor',
                            routing_key='',
                            body=json.dumps(evento_vencedor),
                            properties=pika.BasicProperties(delivery_mode=2)
                        )
                        
                        print(f"[MS Lance] 🏆 Leilão {leilao_id} finalizado. Vencedor: {vencedor['usuario_id']} com R${vencedor['valor']:.2f}")
                    else:
                        print(f"[MS Lance] ⚠️ Leilão {leilao_id} finalizado sem lances")
                    
                    # Remove da memória
                    maiores_lances.pop(leilao_id, None)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[MS Lance] Erro ao processar leilao_finalizado: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        """Inicia o consumo de eventos"""
        try:
            self.connect()
            
            # Configura consumo das filas
            self.channel.basic_consume(
                queue='leilao_iniciado',
                on_message_callback=self.processar_leilao_iniciado
            )
            
            self.channel.basic_consume(
                queue='leilao_finalizado',
                on_message_callback=self.processar_leilao_finalizado
            )
            
            print("[MS Lance] 📡 Consumindo eventos: leilao_iniciado, leilao_finalizado")
            self.channel.start_consuming()
            
        except Exception as e:
            print(f"[MS Lance] Erro no consumidor: {e}")
        finally:
            self.disconnect()

# Inicia thread consumidora
consumidor = ConsumidorEventos()
consumidor.start()

# --- Endpoints REST ---

@app.route('/lances', methods=['POST'])
def receber_lance():
    """Recebe um lance via REST"""
    dados = request.get_json()
    
    if not dados:
        return jsonify({"erro": "Dados não fornecidos"}), 400

    # Validação dos campos obrigatórios
    campos_obrigatorios = ['id', 'usuario_id', 'valor']
    for campo in campos_obrigatorios:
        if campo not in dados:
            return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

    leilao_id = str(dados['id'])
    usuario_id = str(dados['usuario_id'])
    
    try:
        valor = float(dados['valor'])
        if valor <= 0:
            return jsonify({"erro": "Valor do lance deve ser positivo"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "Valor do lance inválido"}), 400

    # Verifica se o leilão está ativo
    with lock_leiloes:
        leiloes_ativos_copy = set(leiloes_ativos)  # Cria cópia para evitar lock durante print
    print(f"[MS Lance] Debug: Verificando leilão {leilao_id} em leiloes_ativos = {leiloes_ativos_copy}")
    
    with lock_leiloes:
        if leilao_id not in leiloes_ativos:
            motivo = f"Leilão não está ativo. Leilões ativos: {list(leiloes_ativos)}"
            publicar_lance_invalidado(leilao_id, usuario_id, valor, motivo)
            return jsonify({"erro": motivo}), 400

    # Verifica se o lance é maior que o último lance
    with lock_leiloes:
        ultimo_lance = maiores_lances.get(leilao_id, {"valor": 0})
        valor_ultimo_lance = ultimo_lance.get("valor", 0)
    
    if valor <= valor_ultimo_lance:
        motivo = f"Lance deve ser maior que R${valor_ultimo_lance:.2f}"
        publicar_lance_invalidado(leilao_id, usuario_id, valor, motivo)
        return jsonify({"erro": motivo}), 400

    # Lance válido - atualiza o maior lance
    with lock_leiloes:
        maiores_lances[leilao_id] = {
            "usuario_id": usuario_id,
            "valor": valor
        }

    # Publica evento lance_validado
    evento_validado = {
        "id": leilao_id,
        "usuario_id": usuario_id,
        "valor": valor
    }
    
    channel = utils.get_rabbitmq_channel()
    channel.basic_publish(
        exchange='',
        routing_key='lance_validado',
        body=json.dumps(evento_validado),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    
    print(f"[MS Lance] ✅ Lance válido: Usuário {usuario_id} - R${valor:.2f} no leilão {leilao_id}")
    
    return jsonify({
        "mensagem": "Lance aceito",
        "id": leilao_id,
        "valor": valor
    }), 200

def publicar_lance_invalidado(leilao_id: str, usuario_id: str, valor: float, motivo: str):
    """Publica evento de lance invalidado"""
    evento_invalidado = {
        "id": leilao_id,
        "usuario_id": usuario_id,
        "valor": valor,
        "motivo": motivo
    }
    
    channel = utils.get_rabbitmq_channel()
    channel.basic_publish(
        exchange='',
        routing_key='lance_invalidado',
        body=json.dumps(evento_invalidado),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    
    print(f"[MS Lance] ❌ Lance invalidado: Usuário {usuario_id} - R${valor:.2f} no leilão {leilao_id} (Motivo: {motivo})")

if __name__ == '__main__':
    print("🚀 MS Lance iniciado na porta 4998")
    print("📡 Aguardando eventos e requisições REST...")
    # use_reloader=False evita que o Flask reinicie e perca o estado das variáveis globais
    app.run(debug=True, port=4998, threaded=True, use_reloader=False)

