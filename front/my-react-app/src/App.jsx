import React, { useState, useEffect } from 'react';
import useSSE from './hooks/useSSE';
import LeilaoList from './components/LeilaoList';
import LeilaoForm from './components/LeilaoForm';

// --- Configuração da API ---
// O API Gateway (servidor Flask) roda na porta 5000 por padrão
const API_BASE_URL = 'http://localhost:5000';
const SSE_ENDPOINT = `${API_BASE_URL}/events/stream`; // Endpoint do Flask-SSE

// Usuário simulado (ID que o servidor deve receber)
const SIMULATED_USER_ID = 'user-abc-123'; 

// --- Componente Principal ---
function App() {
  const [userId, setUserId] = useState(SIMULATED_USER_ID);
  const [notificacoes, setNotificacoes] = useState([]);

  // Use o Hook SSE para obter a última notificação
  const latestNotification = useSSE(SSE_ENDPOINT);

  // Efeito para processar novas notificações
  useEffect(() => {
    if (latestNotification) {
      // Cria uma mensagem legível
      const { type, data } = latestNotification;
      let title = "Notificação Recebida";
      let message = JSON.stringify(data);
      
      try {
          const parsedData = typeof data === 'string' ? JSON.parse(data) : data;

          switch (type) {
              case 'lance_v':
                  title = "Novo Lance Válido!";
                  message = `Leilão ID: ${parsedData.id}, Novo Valor: R$${parsedData.valor.toFixed(2)}`;
                  break;
              case 'lance_inv':
                  title = "Lance Invalidado";
                  message = `Lance R$${parsedData.valor.toFixed(2)} foi recusado (Motivo: ${parsedData.motivo || 'Regra de negócio'}).`;
                  break;
              case 'leilao_v':
                  title = "Leilão Encerrado - Vencedor!";
                  message = `O Leilão ID ${parsedData.leilao_id} foi para o usuário ${parsedData.vencedor_id}.`;
                  break;
              case 'link_p':
                  title = "Link de Pagamento Gerado";
                  message = `Acesse: ${parsedData.link} (ID: ${parsedData.leilao_id})`;
                  if (parsedData.vencedor_id === userId) {
                       window.alert(`PARABÉNS! Link de Pagamento: ${parsedData.link}`);
                  }
                  break;
              case 'status_p':
                  title = `💳 Pagamento ${parsedData.status}`;
                  message = `Status do Pagamento no Leilão ${parsedData.leilao_id}: ${parsedData.status}.`;
                  break;
              default:
                  title = `Evento Desconhecido (${type})`;
                  message = JSON.stringify(parsedData);
          }
      } catch(e) {
          console.error("Erro ao processar notificação:", e);
      }
      
      setNotificacoes(prev => [{ id: Date.now(), title, message, type }, ...prev].slice(0, 5));
    }
  }, [latestNotification, userId]);

  const dismissNotification = (id) => {
    setNotificacoes(prev => prev.filter(n => n.id !== id));
  };


  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <header className="bg-indigo-700 shadow p-4 text-white flex justify-between items-center">
        <h1 className="text-2xl font-bold">Sistema de Leilão - Cliente React</h1>
        <div className="text-sm">
          Conectado como: <span className="font-mono bg-indigo-500 p-1 rounded text-xs">{userId}</span>
        </div>
      </header>

      <main className="container mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Formulário e Lista de Leilões (REST) */}
        <div className="lg:col-span-2 space-y-8">
          <LeilaoForm userId={userId} apiBaseUrl={API_BASE_URL} />
          
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-700 mb-4 border-b pb-2">Lista de Leilões (Simulação)</h2>
            {/* O LeilaoList deve ter um useEffect para dar GET em /leiloes e um POST em /lances */}
            <LeilaoList userId={userId} apiBaseUrl={API_BASE_URL} /> 
          </div>
        </div>

        {/* Coluna Lateral: Notificações em Tempo Real (SSE) */}
        <aside className="lg:col-span-1 space-y-4">
          <div className="text-lg font-bold text-gray-700 border-b pb-2">Eventos em Tempo Real (SSE)</div>
          
          {notificacoes.length > 0 ? (
            <div className="space-y-3">
              {notificacoes.map((n) => (
                <div 
                  key={n.id} 
                  className={`p-4 rounded-lg shadow-md border-l-4 cursor-pointer ${
                    n.type === 'link_p' 
                      ? 'bg-green-100 border-green-500' 
                      : n.type === 'lance_v' 
                      ? 'bg-blue-100 border-blue-500'
                      : 'bg-yellow-100 border-yellow-500'
                  }`}
                  onClick={() => dismissNotification(n.id)}
                >
                  <p className="font-semibold">{n.title}</p>
                  <p className="text-sm text-gray-700">{n.message}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 text-center text-gray-500 bg-white rounded-lg shadow">
              Aguardando eventos do servidor...
            </div>
          )}
        </aside>

      </main>
      
      <script src="https://cdn.tailwindcss.com"></script>
    </div>
  );
}

export default App;