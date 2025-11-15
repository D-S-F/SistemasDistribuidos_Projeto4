import { useState } from 'react';

const generateUUID = () => {
  return 'client-' + Date.now().toString(36) + Math.random().toString(36).substring(2);
};

/**
 * @returns {string} O ID exclusivo da sessão atual.
 */
const useUniqueClientId = () => {
  const [clientId, setClientId] = useState(() => {
    const key = 'auction-session-client-id';
    
    let storedId = sessionStorage.getItem(key);

    if (!storedId) {
      storedId = generateUUID();
      sessionStorage.setItem(key, storedId);
      console.log(`[ID] Novo ID de Sessão (por aba) gerado: ${storedId}`);
    } else {
      console.log(`[ID] ID de Sessão existente encontrado: ${storedId}`);
    }

    return storedId;
  });

  return clientId;
};

export default useUniqueClientId;