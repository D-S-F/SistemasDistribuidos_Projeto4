import pika
import json
#from cryptography.hazmat.primitives.asymmetric import rsa, padding 
#from cryptography.hazmat.primitives import hashes, serialization
#from cryptography.exceptions import InvalidSignature
import os

HOST = 'localhost'

def get_rabbitmq_connection():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=HOST))
    return connection

def setup_queues(channel):
    """Configura todas as filas necessárias para o sistema de leilões"""
    channel.queue_declare(queue='leilao_iniciado', durable=True)
    channel.queue_declare(queue='leilao_finalizado', durable=True)
    channel.queue_declare(queue='lance_validado', durable=True)
    channel.queue_declare(queue='lance_invalidado', durable=True)
    channel.queue_declare(queue='leilao_vencedor', durable=True)
    channel.queue_declare(queue='link_pagamento', durable=True)
    channel.queue_declare(queue='status_pagamento', durable=True)

def get_rabbitmq_channel():
    """Retorna um canal RabbitMQ para uso direto"""
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    setup_queues(channel)
    return channel

# def generate_keys():
#     """Gera chaves pública e privada de acordo com o ID do processo cliente"""
#     private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
#     public_key = private_key.public_key()
#     return private_key, public_key

# def sign_message(private_key, message):
#     """Cria uma assinatura para a mensagem com um hex"""
#     if isinstance(message, dict):
#         message = json.dumps(message, sort_keys=True).encode('utf-8')
        
#     signature = private_key.sign(
#         message,
#         padding.PSS(
#             mgf=padding.MGF1(hashes.SHA256()),
#             salt_length=padding.PSS.MAX_LENGTH
#         ),
#         hashes.SHA256()
#     )
#     return signature

# def verify_signature(public_key, signature, message):
#     if isinstance(message, dict):
#         message = json.dumps(message, sort_keys=True).encode('utf-8')

#     try:
#         public_key.verify(
#             signature,
#             message,
#             padding.PSS(
#                 mgf=padding.MGF1(hashes.SHA256()),
#                 salt_length=padding.PSS.MAX_LENGTH
#             ),
#             hashes.SHA256()
#         )
#         return True
#     except InvalidSignature:
#         return False

# def serialize_public_key(public_key):
#     """Converte uma chave pública para o formato PEM para transporte."""
#     return public_key.public_bytes(
#         encoding=serialization.Encoding.PEM,
#         format=serialization.PublicFormat.SubjectPublicKeyInfo
#     )

# def deserialize_public_key(pem_data):
#     """Converte uma chave pública do formato PEM de volta para um objeto."""
#     return serialization.load_pem_public_key(pem_data)

# def save_key_to_file(key, filename):
#     """Salva uma chave (pública ou privada) em um arquivo no formato PEM."""
#     os.makedirs(os.path.dirname(filename), exist_ok=True)
    
#     pem = None
#     if isinstance(key, rsa.RSAPublicKey):
#         pem = key.public_bytes(
#             encoding=serialization.Encoding.PEM,
#             format=serialization.PublicFormat.SubjectPublicKeyInfo
#         )

#     if pem:
#         with open(filename, 'wb') as pem_out:
#             pem_out.write(pem)

# def load_public_key_from_file(filename):
#     """Carrega uma chave pública de um arquivo PEM."""
#     if not os.path.exists(filename):
#         return None
#     with open(filename, 'rb') as pem_in:
#         pem_data = pem_in.read()
#         return serialization.load_pem_public_key(pem_data)