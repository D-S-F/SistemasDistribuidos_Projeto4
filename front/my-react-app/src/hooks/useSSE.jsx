import { useState, useEffect } from 'react';

/**
 * @param {string} sseUrl
 * @returns {object|null}
 */
const useSSE = (sseUrl) => {
  const [latestEvent, setLatestEvent] = useState(null);

  useEffect(() => {
    console.log(`[SSE] Tentando conectar à stream: ${sseUrl}`);
    const eventSource = new EventSource("events/stream");

    eventSource.onmessage = (event) => {
      setLatestEvent({
        type: event.type,
        data: event.data, 
      });
      console.log(`[SSE] Mensagem Padrão Recebida (${event.type}):`, event.data);
    };

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

    eventSource.onerror = (error) => {
      console.error('[SSE] EventSource Error. Tentando reconexão...');
    };

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