from flask import Flask, jsonify, request
import requests
import uuid
import time
import threading
from typing import Dict
from datetime import datetime

app = Flask(__name__)

# URL do webhook do MS Pagamento
MS_PAGAMENTO_WEBHOOK_URL = "http://localhost:4997/webhook/pagamento"

# Armazenamento em memória das transações
transacoes: Dict[str, Dict] = {}  # {transacao_id: {dados da transação}}

# --- Endpoints REST ---

@app.route('/pagamentos', methods=['POST'])
def criar_transacao():
    """
    Recebe requisição do MS Pagamento para criar uma transação
    Retorna um link de pagamento
    """
    dados = request.get_json()
    
    if not dados:
        return jsonify({"erro": "Dados não fornecidos"}), 400

    # Validação dos campos obrigatórios
    campos_obrigatorios = ['valor', 'moeda', 'cliente_id', 'id']
    for campo in campos_obrigatorios:
        if campo not in dados:
            return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

    # Gera ID único para a transação
    transacao_id = str(uuid.uuid4())
    
    # Cria a transação
    transacao = {
        "transacao_id": transacao_id,
        "id": dados['id'],
        "cliente_id": dados['cliente_id'],
        "valor": float(dados['valor']),
        "moeda": dados.get('moeda', 'BRL'),
        "descricao": dados.get('descricao', ''),
        "status": "pendente",
        "criado_em": datetime.now().isoformat()
    }
    
    transacoes[transacao_id] = transacao
    
    # Gera o link de pagamento
    link_pagamento = f"http://localhost:5001/pagamentos/{transacao_id}/processar"
    
    print(f"[Sistema Externo] ✅ Transação criada: {transacao_id}")
    print(f"   Leilão: {dados['id']}, Cliente: {dados['cliente_id']}, Valor: R${dados['valor']:.2f}")
    print(f"   Link: {link_pagamento}")
    
    return jsonify({
        "transacao_id": transacao_id,
        "link_pagamento": link_pagamento,
        "status": "pendente"
    }), 201

@app.route('/pagamentos/<transacao_id>/processar', methods=['GET', 'POST']) # 1. Adicione 'GET' aqui
def processar_pagamento(transacao_id):
    """
    GET: Mostra a tela de pagamento (HTML).
    POST: Processa o pagamento (JSON ou Form Data).
    """
    
    # --- Lógica para o Navegador (GET) ---
    if request.method == 'GET':
        transacao = transacoes.get(transacao_id)
        if not transacao:
            return "<h1>Transação não encontrada</h1>", 404
            
        if transacao['status'] != 'pendente':
            return f"<h1>Transação já processada: {transacao['status']}</h1>", 400

        # Retorna um HTML simples simulando a tela do Gateway de Pagamento
        return f'''
        <html>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Gateway de Pagamento Simulado</h1>
                <div style="border: 1px solid #ccc; padding: 20px; max-width: 400px; margin: 0 auto;">
                    <p><strong>Loja:</strong> Sistema de Leilão</p>
                    <p><strong>Valor:</strong> {transacao['moeda']} {transacao['valor']:.2f}</p>
                    <p><strong>Descrição:</strong> {transacao.get('descricao', 'Sem descrição')}</p>
                    <hr>
                    <h3>Deseja aprovar esta compra?</h3>
                    
                    <form method="POST" style="display: inline;">
                        <input type="hidden" name="status" value="aprovado">
                        <button type="submit" style="background-color: green; color: white; padding: 10px 20px; border: none; cursor: pointer;">
                            CONFIRMAR PAGAMENTO
                        </button>
                    </form>
                    
                    <form method="POST" style="display: inline; margin-left: 10px;">
                        <input type="hidden" name="status" value="recusado">
                        <button type="submit" style="background-color: red; color: white; padding: 10px 20px; border: none; cursor: pointer;">
                            CANCELAR
                        </button>
                    </form>
                </div>
            </body>
        </html>
        '''

    # --- Lógica de Processamento (POST) ---
    
    # Tenta pegar dados via JSON (se vier de API) ou via FORM (se vier do navegador)
    dados = request.get_json(silent=True) or request.form
    
    if not dados:
        return jsonify({"erro": "Dados não fornecidos"}), 400

    status = dados.get('status')
    
    if not status:
        return jsonify({"erro": "Campo 'status' obrigatório"}), 400

    if status not in ['aprovado', 'recusado']:
        return jsonify({"erro": "Status deve ser 'aprovado' ou 'recusado'"}), 400

    transacao = transacoes.get(transacao_id)
    
    if not transacao:
        return jsonify({"erro": "Transação não encontrada"}), 404

    if transacao['status'] != 'pendente':
        # Se for via navegador, retorna HTML amigável
        if not request.is_json:
            return f"<h1>Erro: Transação já processada ({transacao['status']})</h1>"
        return jsonify({"erro": f"Transação já processada. Status atual: {transacao['status']}"}), 400

    # Atualiza status da transação
    transacao['status'] = status
    transacao['processado_em'] = datetime.now().isoformat()
    
    # Envia webhook ao MS Pagamento (Thread separada)
    threading.Thread(
        target=enviar_webhook,
        args=(transacao,),
        daemon=True
    ).start()
    
    print(f"[Sistema Externo] 💳 Pagamento processado: {transacao_id} - {status.upper()}")
    
    # Resposta final
    if request.is_json:
        # Se quem chamou foi uma API (Postman/cURL)
        return jsonify({
            "transacao_id": transacao_id,
            "status": status,
            "mensagem": f"Pagamento {status} com sucesso"
        }), 200
    else:
        # Se quem chamou foi o Navegador, mostra página de sucesso
        cor = "green" if status == 'aprovado' else "red"
        return f"<h1 style='color: {cor}; text-align: center; margin-top: 50px;'>Pagamento {status.upper()}!</h1><p style='text-align: center;'>Você pode fechar esta janela.</p>"

def enviar_webhook(transacao: Dict):
    """
    Envia notificação assíncrona via webhook ao MS Pagamento
    """
    # Aguarda um pouco para simular processamento
    time.sleep(1)
    
    payload = {
        "transacao_id": transacao['transacao_id'],
        "id": transacao['id'],
        "status": transacao['status'],
        "valor": transacao['valor'],
        "cliente_id": transacao['cliente_id'],
        "moeda": transacao.get('moeda', 'BRL'),
        "processado_em": transacao.get('processado_em', '')
    }
    
    try:
        response = requests.post(
            MS_PAGAMENTO_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[Sistema Externo] ✅ Webhook enviado com sucesso para MS Pagamento")
            print(f"   Transação: {transacao['transacao_id']}, Status: {transacao['status']}")
        else:
            print(f"[Sistema Externo] ⚠️ Webhook retornou status {response.status_code}")
            print(f"   Resposta: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"[Sistema Externo] ❌ Erro ao enviar webhook: {e}")

@app.route('/transacoes', methods=['GET'])
def listar_transacoes():
    """Endpoint auxiliar para listar todas as transações (para debug)"""
    return jsonify(transacoes), 200

@app.route('/transacoes/<transacao_id>', methods=['GET'])
def consultar_transacao(transacao_id):
    """Endpoint para consultar uma transação específica"""
    transacao = transacoes.get(transacao_id)
    
    if not transacao:
        return jsonify({"erro": "Transação não encontrada"}), 404
    
    return jsonify(transacao), 200

if __name__ == '__main__':
    print("🚀 Sistema Externo de Pagamento iniciado na porta 5001")
    print("📡 Endpoint: POST /pagamentos - Criar transação")
    print("📡 Endpoint: POST /pagamentos/<transacao_id>/processar - Processar pagamento")
    print("📡 Webhook configurado para: http://localhost:4997/webhook/pagamento")
    app.run(debug=True, port=5001, threaded=True)
