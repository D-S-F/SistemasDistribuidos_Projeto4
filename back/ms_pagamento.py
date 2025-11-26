from flask import Flask, jsonify, request
import pika
import json
import threading
import requests
import utils
from typing import Dict

app = Flask(__name__)

# URL do sistema externo de pagamentos (simulado)
SISTEMA_PAGAMENTO_URL = "http://localhost:5001"  # Você pode ajustar conforme necessário

# Armazenamento em memória dos pagamentos pendentes
pagamentos_pendentes: Dict[str, Dict] = {}  # {leilao_id: {"vencedor_id": str, "valor": float, "link": str}}

class ConsumidorVencedor(threading.Thread):
    """Thread que consome eventos de leilão vencedor"""
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

    def processar_leilao_vencedor(self, ch, method, properties, body):
        """Processa evento de leilão vencedor e gera link de pagamento"""
        try:
            evento = json.loads(body.decode('utf-8'))
            leilao_id = evento.get('id')
            vencedor_id = evento.get('vencedor_id')
            valor = evento.get('valor')
            
            if not all([leilao_id, vencedor_id, valor]):
                print(f"[MS Pagamento] ⚠️ Evento incompleto: {evento}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            print(f"[MS Pagamento] 🏆 Processando pagamento para leilão {leilao_id}")
            print(f"   Vencedor: {vencedor_id}, Valor: R${valor:.2f}")

            # Faz requisição REST ao sistema externo de pagamentos
            dados_pagamento = {
                "valor": valor,
                "moeda": "BRL",
                "cliente_id": vencedor_id,
                "id": leilao_id,
                "descricao": f"Pagamento do leilão {leilao_id}"
            }

            try:
                # Faz requisição REST ao sistema externo de pagamentos
                response = requests.post(
                    f"{SISTEMA_PAGAMENTO_URL}/pagamentos",
                    json=dados_pagamento,
                    timeout=10
                )
                
                if response.status_code == 201:
                    resposta = response.json()
                    link_pagamento = resposta.get('link_pagamento')
                    transacao_id = resposta.get('transacao_id')
                    
                    if not link_pagamento:
                        raise Exception("Link de pagamento não retornado pelo sistema externo")
                    
                    # Armazena informações do pagamento
                    pagamentos_pendentes[leilao_id] = {
                        "vencedor_id": vencedor_id,
                        "valor": valor,
                        "link": link_pagamento,
                        "transacao_id": transacao_id
                    }

                    # Publica evento link_pagamento
                    evento_link = {
                        "id": leilao_id,
                        "vencedor_id": vencedor_id,
                        "link": link_pagamento,
                        "valor": valor
                    }

                    self.channel.basic_publish(
                        exchange='',
                        routing_key='link_pagamento',
                        body=json.dumps(evento_link),
                        properties=pika.BasicProperties(delivery_mode=2)
                    )

                    print(f"[MS Pagamento] ✅ Link de pagamento gerado para leilão {leilao_id}")
                    print(f"   Link: {link_pagamento}")
                    print(f"   Transação ID: {transacao_id}")
                else:
                    raise Exception(f"Sistema externo retornou status {response.status_code}: {response.text}")

            except requests.exceptions.RequestException as e:
                print(f"[MS Pagamento] ❌ Erro ao comunicar com sistema externo: {e}")
                # Publica evento de erro
                evento_erro = {
                    "id": leilao_id,
                    "vencedor_id": vencedor_id,
                    "erro": f"Erro de comunicação: {str(e)}"
                }
                self.channel.basic_publish(
                    exchange='',
                    routing_key='link_pagamento',
                    body=json.dumps(evento_erro),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
            except Exception as e:
                print(f"[MS Pagamento] ❌ Erro ao gerar link de pagamento: {e}")
                # Publica evento de erro
                evento_erro = {
                    "id": leilao_id,
                    "vencedor_id": vencedor_id,
                    "erro": str(e)
                }
                self.channel.basic_publish(
                    exchange='',
                    routing_key='link_pagamento',
                    body=json.dumps(evento_erro),
                    properties=pika.BasicProperties(delivery_mode=2)
                )

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[MS Pagamento] Erro ao processar leilao_vencedor: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        """Inicia o consumo de eventos"""
        try:
            self.connect()
            
            exchange = self.channel.queue_declare(queue='', exclusive=True)
            self.aux_queue = exchange.method.queue
            self.channel.queue_bind(exchange='leilao_vencedor', queue=self.aux_queue)

            self.channel.basic_consume(
                queue=self.aux_queue,
                on_message_callback=self.processar_leilao_vencedor
            )
            
            print("[MS Pagamento] 📡 Consumindo eventos: leilao_vencedor")
            self.channel.start_consuming()
            
        except Exception as e:
            print(f"[MS Pagamento] Erro no consumidor: {e}")
        finally:
            self.disconnect()


# Inicia thread consumidora
consumidor = ConsumidorVencedor()
consumidor.start()

# --- Endpoints REST ---

@app.route('/webhook/pagamento', methods=['POST'])
def webhook_pagamento():
    """
    Endpoint que recebe notificações assíncronas do sistema externo
    indicando o status da transação (aprovada ou recusada)
    """
    dados = request.get_json()
    
    if not dados:
        return jsonify({"erro": "Dados não fornecidos"}), 400

    # Campos esperados do webhook
    leilao_id = dados.get('id')
    status = dados.get('status')  # 'aprovado' ou 'recusado'
    transacao_id = dados.get('transacao_id', '')
    
    if not leilao_id or not status:
        return jsonify({"erro": "Campos obrigatórios ausentes: leilao_id, status"}), 400

    if status not in ['aprovado', 'recusado']:
        return jsonify({"erro": "Status inválido. Deve ser 'aprovado' ou 'recusado'"}), 400

    # Busca informações do pagamento
    pagamento = pagamentos_pendentes.get(leilao_id)
    
    if not pagamento:
        print(f"[MS Pagamento] ⚠️ Pagamento não encontrado para leilão {leilao_id}")
        return jsonify({"erro": "Pagamento não encontrado"}), 404

    # Publica evento status_pagamento
    evento_status = {
        "id": leilao_id,
        "vencedor_id": pagamento.get("vencedor_id"),
        "status": status,
        "valor": pagamento.get("valor"),
        "transacao_id": transacao_id
    }

    channel = utils.get_rabbitmq_channel()
    channel.basic_publish(
        exchange='',
        routing_key='status_pagamento',
        body=json.dumps(evento_status),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    print(f"[MS Pagamento] 📢 Status do pagamento publicado: Leilão {leilao_id} - {status.upper()}")
    
    # Remove da lista de pendentes se aprovado
    if status == 'aprovado':
        pagamentos_pendentes.pop(leilao_id, None)

    return jsonify({
        "mensagem": f"Status do pagamento processado: {status}",
        "id": leilao_id
    }), 200

@app.route('/pagamentos/pendentes', methods=['GET'])
def listar_pagamentos_pendentes():
    """Endpoint auxiliar para listar pagamentos pendentes (para debug)"""
    return jsonify(pagamentos_pendentes), 200

if __name__ == '__main__':
    print("🚀 MS Pagamento iniciado na porta 4997")
    print("📡 Aguardando eventos e webhooks...")
    print(f"🌐 Webhook disponível em: http://localhost:4997/webhook/pagamento")
    app.run(debug=True, port=4997, threaded=True)

