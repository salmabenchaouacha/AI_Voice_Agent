import { useCallback, useEffect, useRef, useState } from 'react';

const REPLY_TIMEOUT_MS = 60000;
const HISTORY_KEY = 'va.history.v1';
const HISTORY_MAX = 100;

const ERR_SERVER = "Serveur injoignable. Lance « python server.py » dans le dossier backend, puis recharge la page.";

let seq = 0;
const mk = (role, text, extra = {}) => ({ id: `${Date.now()}-${seq++}`, role, text, time: new Date().toISOString(), ...extra });

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; } catch { return []; }
}

/**
 * Tout ce qui touche au serveur :
 *  - WebSocket (reconnexion automatique)
 *  - envoi de commandes écrites
 *  - historique persistant
 */
export function useAssistant({ speak, stopSpeaking }) {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | thinking
  const [messages, setMessages] = useState(loadHistory);
  const [error, setError] = useState('');

  const wsRef = useRef(null);
  const statusRef = useRef(status);
  const replyTimer = useRef(null);
  const handlerRef = useRef(null);
  statusRef.current = status;

  const add = useCallback((msg) => setMessages((m) => [...m, msg].slice(-HISTORY_MAX)), []);

  useEffect(() => {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(messages)); } catch { /* ignoré */ }
  }, [messages]);

  const armReplyTimeout = useCallback(() => {
    clearTimeout(replyTimer.current);
    replyTimer.current = setTimeout(() => {
      setStatus('idle');
      setError('Le serveur met trop de temps à répondre. Vérifie le terminal du backend.');
    }, REPLY_TIMEOUT_MS);
  }, []);

  // Réception des messages serveur (fonction recréée à chaque rendu pour voir le dernier `speak`)
  handlerRef.current = (data) => {
    if (data.type === 'result') {
      clearTimeout(replyTimer.current);
      if (data.source === 'voice' && data.heard) add(mk('user', data.heard, { via: 'voice' }));
      add(mk('assistant', data.reply));
      setStatus('idle');
      speak(data.reply);
    } else if (data.type === 'notification') {
      add(mk('notice', data.text));
      speak(data.text);
    }
  };

  // Connexion WebSocket + reconnexion
  useEffect(() => {
    let stopped = false;
    let retry;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
      wsRef.current = ws;
      ws.onopen = () => { setConnected(true); setError((e) => (e === ERR_SERVER ? '' : e)); };
      ws.onmessage = (e) => {
        try { handlerRef.current(JSON.parse(e.data)); } catch { /* message illisible */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (statusRef.current === 'thinking') {
          clearTimeout(replyTimer.current);
          setStatus('idle');
          setError('Connexion perdue pendant la réponse. Réessaie.');
        }
        if (!stopped) retry = setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      clearTimeout(replyTimer.current);
      wsRef.current?.close();
    };
  }, []);

  const socketReady = () => wsRef.current?.readyState === WebSocket.OPEN;

  const sendText = useCallback((raw) => {
    const text = raw.trim();
    if (!text || statusRef.current !== 'idle') return;
    if (!socketReady()) { setError(ERR_SERVER); return; }
    stopSpeaking();
    setError('');
    add(mk('user', text, { via: 'text' }));
    setStatus('thinking');
    wsRef.current.send(JSON.stringify({ type: 'text', text }));
    armReplyTimeout();
  }, [add, armReplyTimeout, stopSpeaking]);

  const clearHistory = useCallback(() => setMessages([]), []);
  const dismissError = useCallback(() => setError(''), []);

  return { connected, status, messages, error, sendText, clearHistory, dismissError };
}