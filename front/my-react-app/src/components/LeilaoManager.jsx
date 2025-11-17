import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:5000';

/**
 * @param {object} props
 * @param {string} props.cliente_id
 */
function LeilaoManager({ cliente_id }) {
  const [leiloesAtivos, setLeiloesAtivos] = useState([]);
  const [meusInteresses, setMeusInteresses] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchLeiloesAtivos = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/leiloes/ativos`);
      if (!response.ok) {
        throw new Error(`Erro ao buscar leilões: ${response.statusText}`);
      }
      const data = await response.json();
      setLeiloesAtivos(data || []);
    } catch (err) {
      setError(err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Envia um pedido para SEGUIR um leilão.
   * @param {string} leilao_id
   */
  const handleSeguir = async (leilao_id) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/interest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cliente_id, leilao_id: String(leilao_id) }),
      });
      if (!response.ok) {
        throw new Error('Não foi possível seguir o leilão.');
      }
      
      // Atualiza o estado local da UI
      setMeusInteresses(prevInteresses => new Set(prevInteresses).add(String(leilao_id)));

    } catch (err) {
      setError(err.message);
    }
  };

  /**
   * Envia um pedido para DEIXAR DE SEGUIR um leilão.
   * @param {string} leilao_id
   */
  const handleDeixarDeSeguir = async (leilao_id) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/interest`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cliente_id, leilao_id: String(leilao_id) }),
      });
      if (!response.ok) {
        throw new Error('Não foi possível deixar de seguir o leilão.');
      }
      
      // Atualiza o estado local da UI
      setMeusInteresses(prevInteresses => {
        const novoSet = new Set(prevInteresses);
        novoSet.delete(String(leilao_id));
        return novoSet;
      });

    } catch (err) {
      setError(err.message);
    }
  };

  // --- Efeitos ---

  useEffect(() => {
    fetchLeiloesAtivos();
  }, []);

  
  // --- Renderização ---

  const renderConteudo = () => {
    if (loading) {
      return <p className="text-gray-400">A carregar leilões...</p>;
    }

    if (error) {
      return <p className="text-red-500">Erro: {error}</p>;
    }

    if (leiloesAtivos.length === 0) {
      return <p className="text-gray-400">Nenhum leilão ativo encontrado.</p>;
    }

    return (
      <ul className="divide-y divide-gray-700">
        {leiloesAtivos.map((leilao) => {
          const estouAseguir = meusInteresses.has(String(leilao.id));
          return (
            <li key={leilao.id} className="py-3 flex justify-between items-center">
              <div>
                <p className="font-semibold">{leilao.desc || 'Leilão sem descrição'}</p>
                <p className="text-sm text-gray-400">ID: {leilao.id}</p>
              </div>
              
              <button
                onClick={() => estouAseguir ? handleDeixarDeSeguir(leilao.id) : handleSeguir(leilao.id)}
                className={`px-3 py-1 text-sm rounded-full ${
                  estouAseguir
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
              >
                {estouAseguir ? 'Deixar de Seguir' : 'Seguir'}
              </button>
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <div className="bg-gray-800 text-white p-4 rounded-lg shadow-lg max-w-md mx-auto mt-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Leilões Ativos</h2>
        <button
          onClick={fetchLeiloesAtivos}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded-lg text-sm disabled:opacity-50"
        >
          {loading ? 'A carregar...' : 'Atualizar'}
        </button>
      </div>
      
      <div className="space-y-2">
        {renderConteudo()}
      </div>
    </div>
  );
}

export default LeilaoManager;