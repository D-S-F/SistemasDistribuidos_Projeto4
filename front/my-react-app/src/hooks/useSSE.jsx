import { useState, useEffect } from 'react';

/**
 * Hook customizado para gerenciar a conexão Server-Sent Events (SSE).
 * @param {string} sseUrl - URL completa do endpoint SSE (ex: http://localhost:5000/events/stream).
 * @returns {object|null}
 */
const useSSE = (sseUrl) => {
  const [latestEvent, setLatestEvent] = useState(null);

  useEffect(() => {
    // Cria a conexão EventSource
    console.log(`[SSE] Tentando conectar à stream: ${sseUrl}`);
    const eventSource = new EventSource("http://localhost:5000/events");

    // Listener para o evento padrão 'message' (fallback/geral)
    eventSource.onmessage = (event) => {
      setLatestEvent({
        type: event.type,
        data: event.data, 
      });
      console.log(`[SSE] Mensagem Padrão Recebida (${event.type}):`, event.data);
    };

    // Listener para Eventos Customizados (Tipos definidos pelo seu backend Python)
    const eventTypes = ['lance_v', 'lance_inv', 'leilao_v', 'link_p', 'status_p'];

    const handleCustomEvent = (event) => {
        setLatestEvent({
            type: event.type,
            data: event.data,
        });
        console.log(`[SSE] Evento Customizado Recebido (${event.type}):`, event.data);
    };

    eventTypes.forEach(type => {
        eventSource.addEventListener(type, handleCustomEvent);
    });


    // Trata erros de conexão
    eventSource.onerror = (error) => {
      console.error('[SSE] EventSource Error. Tentando reconexão...');
    };

    // Cleanup: Fecha a conexão quando o componente é desmontado
    return () => {
      console.log('[SSE] Conexão encerrada.');
      eventSource.close();
      eventTypes.forEach(type => {
        eventSource.removeEventListener(type, handleCustomEvent);
      });
    };

  }, [sseUrl]); 

  return latestEvent;
};

export default useSSE;