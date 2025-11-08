import { useState } from 'react';

// Função utilitária para gerar um UUID V4 (simulação simples)
const generateUUID = () => {
  return 'client-' + Date.now().toString(36) + Math.random().toString(36).substring(2);
};

/**
 * Hook customizado para obter um ID único para cada ABA/JANELA do navegador (sessão).
 * Se o usuário fechar a aba, o ID é perdido.
 * @returns {string} O ID exclusivo da sessão atual.
 */
const useUniqueClientId = () => {
  const [clientId, setClientId] = useState(() => {
    // CHAVE ALTERADA: Agora usamos sessionStorage, que é exclusivo por aba/janela.
    const key = 'auction-session-client-id';
    
    // 1. Tenta buscar o ID existente no sessionStorage
    let storedId = sessionStorage.getItem(key);

    if (!storedId) {
      // 2. Se não existir (nova aba/janela), gera um novo ID
      storedId = generateUUID();
      // 3. Armazena no sessionStorage para o ciclo de vida desta aba
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