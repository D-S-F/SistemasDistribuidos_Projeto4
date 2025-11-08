import React, { useState, useEffect } from 'react';

function LeilaoList({ userId, apiBaseUrl }) {
    // 1. O estado inicial agora é um array vazio.
    const [leiloes, setLeiloes] = useState([]);
    const [lanceValor, setLanceValor] = useState({});
    const [statusMensagem, setStatusMensagem] = useState({});
    const [carregando, setCarregando] = useState(true);
    const [erroCarga, setErroCarga] = useState(null);

    // Efeito para buscar os leilões ativos quando o componente é montado
    useEffect(() => {
        const fetchLeiloes = async () => {
            setCarregando(true);
            setErroCarga(null);
            
            try {
                // Requisição GET para buscar leilões ativos (Assume que o Gateway tem esta rota)
                // O API Gateway deve rotear para o Serviço de Leilões
                const response = await fetch(`${apiBaseUrl}/leiloes/ativos`);

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.erro || `Falha na busca: HTTP ${response.status}`);
                }

                const data = await response.json();
                
                // Assumindo que o backend retorna uma lista de objetos leilão
                if (Array.isArray(data)) {
                    setLeiloes(data);
                } else {
                    throw new Error("Formato de dados inesperado do servidor.");
                }
                
            } catch (error) {
                console.error("Erro ao carregar leilões:", error);
                setErroCarga(`Erro ao carregar leilões: ${error.message}`);
            } finally {
                setCarregando(false);
            }
        };

        fetchLeiloes();
        
        // Retorno vazio, pois a busca é apenas na montagem
    }, [apiBaseUrl]); // Roda apenas na montagem e se a URL da API mudar

    const handleLanceChange = (id, value) => {
        setLanceValor(prev => ({ ...prev, [id]: value }));
    };

    const handleFazerLance = async (leilaoId) => {
        const valor = parseFloat(lanceValor[leilaoId]);
        
        if (isNaN(valor) || valor <= 0) return setStatusMensagem(prev => ({ ...prev, [leilaoId]: 'Insira um valor válido.' }));

        setStatusMensagem(prev => ({ ...prev, [leilaoId]: 'Enviando lance...' }));

        try {
            // A requisição POST vai para a rota /lances do seu API Gateway (Flask)
            const response = await fetch(`${apiBaseUrl}/lances`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': userId, 
                },
                body: JSON.stringify({
                    id: leilaoId, 
                    valor: valor,
                    usuario_id: userId
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.erro || `Falha no envio: HTTP ${response.status}`);
            }

            // Sucesso: a confirmação virá via SSE
            setStatusMensagem(prev => ({ ...prev, [leilaoId]: `Lance R$${valor} enviado! Aguarde confirmação em tempo real.` }));
            setLanceValor(prev => ({ ...prev, [leilaoId]: '' }));

        } catch (error) {
            setStatusMensagem(prev => ({ ...prev, [leilaoId]: `Erro: ${error.message}` }));
        }
    };


    if (carregando) {
        return <div className="text-center py-8 text-gray-500">A carregar leilões...</div>;
    }
    
    if (erroCarga) {
        return <div className="text-center py-8 text-red-600 font-semibold">{erroCarga}</div>;
    }

    if (leiloes.length === 0) {
        return <div className="text-center py-8 text-gray-500">Nenhum leilão ativo encontrado. Crie um novo acima!</div>;
    }

    return (
        <div className="space-y-4">
            {leiloes.map((leilao) => (
                <div key={leilao.id} className="p-4 border border-gray-200 rounded-md flex justify-between items-center bg-white shadow-sm">
                    <div>
                        <h3 className="text-lg font-bold text-gray-800">{leilao.nome}</h3>
                        {/* Certifique-se de que a estrutura de dados do backend corresponde a isto */}
                        <p className="text-sm text-gray-600">Lance Atual: <span className="font-semibold text-red-600">R${leilao.lance_atual?.valor ? leilao.lance_atual.valor.toFixed(2) : leilao.valor_inicial.toFixed(2)}</span></p>
                        <p className="text-xs text-gray-500">Último lance por: {leilao.lance_atual?.usuario || 'N/A'}</p>
                    </div>
                    <div className="flex flex-col items-end space-y-2">
                        <div className="flex items-center space-x-2">
                            <input
                                type="number"
                                step="0.01"
                                placeholder="Seu lance"
                                value={lanceValor[leilao.id] || ''}
                                onChange={(e) => handleLanceChange(leilao.id, e.target.value)}
                                className="w-32 border border-gray-300 rounded-md p-2 text-sm focus:ring-indigo-500 focus:border-indigo-500"
                            />
                            <button
                                onClick={() => handleFazerLance(leilao.id)}
                                className="py-2 px-4 rounded-md text-white text-sm font-medium bg-indigo-600 hover:bg-indigo-700"
                            >
                                Dar Lance
                            </button>
                        </div>
                        {statusMensagem[leilao.id] && 
                            <p className="text-xs mt-1 text-gray-500">{statusMensagem[leilao.id]}</p>}
                    </div>
                </div>
            ))}
        </div>
    );
}

export default LeilaoList;