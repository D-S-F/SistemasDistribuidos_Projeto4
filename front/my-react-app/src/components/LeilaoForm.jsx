import React, { useState } from 'react';

function LeilaoForm({ userId, apiBaseUrl }) {
    const [descricao, setDescricao] = useState('');
    // REMOVIDO: const [valorInicial, setValorInicial] = useState('');
    
    // NOVO: Estado para armazenar a data e hora de finalização
    const [horaFinalizacao, setHoraFinalizacao] = useState('');
    
    const [mensagem, setMensagem] = useState(null);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setMensagem({ text: 'Criando leilão...', type: 'loading' });

        // Estrutura de dados atualizada
        const novoLeilao = {
            desc: descricao,
            // REMOVIDO: valor: parseFloat(valorInicial),
            
            // NOVO: Envia a hora de finalização
            hora_finalizacao: horaFinalizacao, 
            
            criador_id: userId,
            id: Date.now() 
        };

        try {
            // Requisição POST para a rota /leiloes do seu API Gateway
            const response = await fetch(`${apiBaseUrl}/leiloes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': userId, 
                },
                body: JSON.stringify(novoLeilao),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.erro || `Falha na criação: HTTP ${response.status}`);
            }

            const data = await response.json();
            setMensagem({ text: `Leilão '${data.desc}' criado com sucesso! ID: ${data.id}`, type: 'success' });
            setDescricao('');
            setHoraFinalizacao(''); // Limpa o campo de hora

        } catch (error) {
            setMensagem({ text: `Erro ao criar leilão: ${error.message}`, type: 'error' });
        }
    };

    return (
        <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-700 mb-4 border-b pb-2">Criar Novo Leilão</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-gray-700">Descrição</label>
                    <input
                        type="text"
                        value={descricao}
                        onChange={(e) => setDescricao(e.target.value)}
                        placeholder="Ex: Vaso Chinês do Século XIV"
                        required
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    />
                </div>
                
                {/* INÍCIO DO NOVO CAMPO: HORA DE FINALIZAÇÃO */}
                <div>
                    <label className="block text-sm font-medium text-gray-700">Hora de Finalização</label>
                    <input
                        type="datetime-local" // Permite selecionar Data e Hora
                        value={horaFinalizacao}
                        onChange={(e) => setHoraFinalizacao(e.target.value)}
                        required
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    />
                </div>
                {/* FIM DO NOVO CAMPO */}
                
                <button
                    type="submit"
                    className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                    Publicar Leilão
                </button>
            </form>
            {mensagem && (
                <p className={`mt-4 p-2 text-sm rounded ${
                    mensagem.type === 'success' ? 'bg-green-100 text-green-700' : 
                    mensagem.type === 'error' ? 'bg-red-100 text-red-700' : 
                    'bg-blue-100 text-blue-700'
                }`}>
                    {mensagem.text}
                </p>
            )}
        </div>
    );
}

export default LeilaoForm;