import React, { useState } from 'react';

function LeilaoList({ userId, apiBaseUrl }) {
    const [leilaoId, setLeilaoId] = useState('');
    const [lanceValor, setLanceValor] = useState('');
    const [statusMensagem, setStatusMensagem] = useState(null);

    const handleFazerLance = async (event) => {
        event.preventDefault(); // Impede o recarregamento da página
        const valor = parseFloat(lanceValor);
        
        if (!leilaoId || isNaN(valor) || valor <= 0) {
            setStatusMensagem({ text: 'Por favor, insira um ID de leilão e um valor válido.', type: 'error' });
            return;
        }

        setStatusMensagem({ text: 'Enviando lance...', type: 'loading' });

        try {
            // A requisição POST vai para a rota /lances do seu API Gateway (Flask)
            const response = await fetch(`${apiBaseUrl}/lances`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': userId, // Identificador único da sessão/usuário
                },
                body: JSON.stringify({
                    id: leilaoId,      // ID do Leilão
                    valor: valor,      // Novo Valor
                    usuario_id: userId // O usuário que fez o lance
                }),
            });

            if (!response.ok) {
                // Tratamento de erro do fetch
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.erro || `Falha no envio: HTTP ${response.status}`);
            }

            // Sucesso: a confirmação de lance deve vir via SSE
            setStatusMensagem({ text: `Lance R$${valor.toFixed(2)} enviado para o Leilão ${leilaoId}! Aguarde confirmação em tempo real.`, type: 'success' });
            setLanceValor(''); // Limpa apenas o campo de valor
            // Mantém o ID do leilão para facilitar o envio de lances subsequentes

        } catch (error) {
            setStatusMensagem({ text: `Erro no envio: ${error.message}`, type: 'error' });
        }
    };


    return (
        <div className="p-6 border border-gray-200 rounded-md bg-white shadow-lg">
            <h2 className="text-xl font-semibold text-gray-700 mb-4 border-b pb-2">Realizar Novo Lance</h2>
            
            <form onSubmit={handleFazerLance} className="space-y-4">
                
                {/* Campo ID do Leilão */}
                <div>
                    <label className="block text-sm font-medium text-gray-700">ID do Leilão</label>
                    <input
                        type="text"
                        placeholder="ID do Leilão (Ex: 1700...)"
                        value={leilaoId}
                        onChange={(e) => setLeilaoId(e.target.value)}
                        required
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    />
                </div>

                {/* Campo Valor do Lance */}
                <div>
                    <label className="block text-sm font-medium text-gray-700">Valor do Lance (R$)</label>
                    <input
                        type="number"
                        step="0.01"
                        placeholder="Ex: 1500.00"
                        value={lanceValor}
                        onChange={(e) => setLanceValor(e.target.value)}
                        required
                        className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    />
                </div>
                
                <button
                    type="submit"
                    className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                    Realizar Lance
                </button>
            </form>
            
            {statusMensagem && (
                <p className={`mt-4 p-2 text-sm rounded ${
                    statusMensagem.type === 'success' ? 'bg-green-100 text-green-700' : 
                    statusMensagem.type === 'error' ? 'bg-red-100 text-red-700' : 
                    'bg-blue-100 text-blue-700'
                }`}>
                    {statusMensagem.text}
                </p>
            )}
        </div>
    );
}

export default LeilaoList;