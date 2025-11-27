from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sse import sse
import requests
import threading
import pika
import utils
import redis
import json

# --- Configurações ---
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost:6379"

CORS(
    app,
    resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:5173"]}},
    supports_credentials=False,
)
# -------------------------------------

LEILAO_SERVICE_URL = 'http://localhost:4999'
LANCE_SERVICE_URL = 'http://localhost:4998' 

app.register_blueprint(sse, url_prefix='/events/stream')

interests = {}

## RabbitMQ ##

class RabbitMQConsumer(threading.Thread):
    def __init__(self, app_context):
        super().__init__()
        self.daemon = True
        self.app_context = app_context
        self.connection = None
        self.channel = None
        self.aux_queue = None

    def connect(self):
        print("[RabbitMQ] Conectando...")
        self.connection = utils.get_rabbitmq_connection()
        self.channel = self.connection.channel()
        utils.setup_queues(self.channel)
        exchange = self.channel.queue_declare(queue='', exclusive=True)
        self.aux_queue = exchange.method.queue
        self.channel.queue_bind(exchange='leilao_vencedor', queue=self.aux_queue)
        print("[RabbitMQ] Conectado e filas configuradas.")


    def disconnect(self):
        if self.connection and self.connection.is_open:
            self.connection.close()

    def publish_sse_event(self, body, event_type):
        with self.app_context:
            try:
                message = body.decode('utf-8')
                print(f"[SSE] Publicando evento {event_type} para o Redis: {message}")

                evento = json.loads(message)

                leilao_id = evento.get('id')
                if not leilao_id:
                    print(f"[AVISO SSE] Evento {event_type} recebido SEM 'leilao_id'. Mensagem: {message}")
                    return

                lista_de_interessados = interests.get(leilao_id)

                if not lista_de_interessados:
                    print(f"[AVISO SSE] Evento {event_type} para leilão {leilao_id}, mas ninguém está a seguir.")
                    return

                print(f"[SSE] Enviando {event_type} para {len(lista_de_interessados)} seguidores do leilão {leilao_id}...")
                for cliente in lista_de_interessados:
                    sse.publish(message, type=event_type, channel=cliente)

                print(f"[SSE] Evento {event_type} publicado com sucesso")

            except json.JSONDecodeError as json_err:
                print(f"[ERRO SSE] Mensagem recebida não é um JSON válido: {body.decode('utf-8')} | Erro: {json_err}")
            except Exception as e:
                print(f"[ERRO SSE] Falha inesperada ao publicar: {e}")
                
    # Métodos de Callback
    
    def processar_lance_validado(self, ch, method, properties, body):
        self.publish_sse_event(body, event_type='lance_v')
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def processar_lance_invalidado(self, ch, method, properties, body):
        self.publish_sse_event(body, event_type='lance_inv')
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def processar_leilao_vencedor(self, ch, method, properties, body):
        self.publish_sse_event(body, event_type='leilao_v')
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def processar_link_pagamento(self, ch, method, properties, body):
        self.publish_sse_event(body, event_type='link_p')
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def processar_status_pagamento(self, ch, method, properties, body):
        self.publish_sse_event(body, event_type='status_p')
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        print("[RabbitMQ] Thread consumidora iniciada.")
        while True:
            try:
                self.connect()
                queues_callbacks = {
                    'lance_validado': self.processar_lance_validado,
                    'lance_invalidado': self.processar_lance_invalidado,
                    self.aux_queue: self.processar_leilao_vencedor,
                    'link_pagamento': self.processar_link_pagamento,
                    'status_pagamento': self.processar_status_pagamento,
                }
                for queue_name, callback in queues_callbacks.items():
                    self.channel.basic_consume(
                        queue=queue_name,
                        on_message_callback=callback
                    )
                    print(f"[RabbitMQ] Consumindo fila: '{queue_name}'")
                print("[RabbitMQ] Aguardando mensagens...")
                self.channel.start_consuming()
            except pika.exceptions.ConnectionClosedByBroker:
                print("[RabbitF_MQ] Conexão fechada pelo broker. Tentando reconectar em 5s...")
            except pika.exceptions.AMQPChannelError as e:
                print(f"[RabbitMQ] Erro no canal AMQP: {e}. Reconectando em 5s...")
            except Exception as e:
                print(f"[RabbitMQ] Erro fatal no thread consumidor: {e}. Reconectando em 5s...")
            finally:
                self.disconnect()
                import time
                time.sleep(5)

## Rest ##

@app.route('/leiloes', methods=['POST'])
def add_leilao():
    novo_leilao = request.get_json()
    print(f"Adicionando novo leilao: {novo_leilao.get('id')} | {novo_leilao.get('desc')}")
    try:
        response = requests.post(f'{LEILAO_SERVICE_URL}/leiloes', json=novo_leilao)
        response.raise_for_status()
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": f"Erro de comunicação com Serviço Leilão: {e}"}), 503

@app.route('/lances', methods=['POST'])
def add_lance():
    novo_lance = request.get_json()
    print(f"Novo lance realizado no leilao {novo_lance.get('id')} de {novo_lance.get('valor')} reais")
    try:
        response = requests.post(f'{LANCE_SERVICE_URL}/lances', json=novo_lance, timeout=10)
        try:
            return jsonify(response.json()), response.status_code
        except requests.exceptions.JSONDecodeError:
            return jsonify({"erro": response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": f"Erro de comunicação com Serviço Lance: {e}"}), 503
    
@app.route('/interest', methods=['POST'])
def add_interest():
    interest = request.get_json()
    leilao_id = interest.get('leilao_id')
    cliente_id = interest.get('cliente_id')
    if not cliente_id or not leilao_id:
        return jsonify({"erro": "Faltam cliente_id ou leilao_id"}), 400

    lista_de_interessados = interests.get(leilao_id)

    if lista_de_interessados is not None:
        if cliente_id not in lista_de_interessados:
            lista_de_interessados.append(cliente_id)
    else:
        interests[leilao_id] = [cliente_id]

    return jsonify({"sucesso": f"Cliente {cliente_id} a seguir o leilão {leilao_id}"})
        
@app.route('/interest', methods=['DELETE'])
def del_interest():
    data = request.get_json()
    leilao_id = data.get('leilao_id')
    cliente_id = data.get('cliente_id')

    if not leilao_id or not cliente_id:
        return jsonify({"erro": "Faltam cliente_id ou leilao_id"}), 400

    lista_de_interessados = interests.get(leilao_id)

    if lista_de_interessados is None:
        return jsonify({"aviso": "Leilão não encontrado nos interesses"}), 404

    if cliente_id in lista_de_interessados:
        lista_de_interessados.remove(cliente_id)
        
        print(f"[interesses] Interesse removido de {cliente_id} por {leilao_id}")
        
        if not lista_de_interessados:
            del interests[leilao_id]
            print(f"[interesses] Lista do leilão {leilao_id} removida por estar vazia.")

        return jsonify({"sucesso": "Interesse removido"}), 200
    else:
        return jsonify({"aviso": "Cliente não estava na lista de interesses"}), 200


@app.route('/leiloes/ativos', methods=['GET'])
def get_leiloes_ativos():
    try:
        response = requests.get(f'{LEILAO_SERVICE_URL}/leiloes')
        response.raise_for_status() 
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": f"Erro de comunicação com Serviço Leilão: {e}"}), 503

if __name__ == '__main__':
    try:
        redis_client = redis.from_url(app.config['REDIS_URL'])
        redis_client.ping()
        print(f"Redis conectado com sucesso em: {app.config['REDIS_URL']}")
    except Exception as e:
        print(f"AVISO: Não foi possível conectar ao Redis: {e}")
    
    app_context = app.app_context() 

    consumer_thread = RabbitMQConsumer(app_context)
    consumer_thread.start()
    
    print("Iniciando API Gateway (Flask)...")
    
    app.run(debug=True, threaded=True, port=5000, use_reloader=False)