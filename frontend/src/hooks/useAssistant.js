import { useCallback, useEffect, useRef, useState } from 'react';

const SPEECH_RMS = 0.02;        // seuil de détection de la voix (0 à 1) : à monter si le bruit ambiant déclenche
const SILENCE_MS = 1100;        // silence qui termine l'enregistrement
const NO_SPEECH_MS = 6000;      // abandon si personne ne parle
const MAX_RECORD_MS = 20000;
const REPLY_TIMEOUT_MS = 60000;
const HISTORY_KEY = 'va.history.v1';
const HISTORY_MAX = 100;

const ERR_SERVER = "Serveur injoignable. Lance « python server.py » dans le dossier backend, puis recharge la page.";
const ERR_MIC_DENIED = "Micro refusé. Autorise le micro dans la barre d'adresse du navigateur, puis réessaie.";
const ERR_NO_MIC_API = "Le navigateur bloque le micro sur cette adresse. Ouvre l'app sur http://localhost:5173.";

let seq = 0;
const mk = (role, text, extra = {}) => ({ id: `${Date.now()}-${seq++}`, role, text, time: new Date().toISOString(), ...extra });

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; } catch { return []; }
}

function pickMime() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
  return candidates.find((m) => window.MediaRecorder?.isTypeSupported?.(m)) || '';
}

/**
 * Tout ce qui touche au serveur et au micro :
 *  - WebSocket (reconnexion automatique)
 *  - enregistrement MediaRecorder avec arrêt automatique au silence
 *  - historique persistant
 */
export function useAssistant({ speak, stopSpeaking }) {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | listening | thinking
  const [messages, setMessages] = useState(loadHistory);
  const [error, setError] = useState('');

  const wsRef = useRef(null);
  const analyserRef = useRef(null);   // lu par l'orbe pour l'animation
  const sessionRef = useRef(null);    // { finish(cancel) } pendant un enregistrement
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
      sessionRef.current?.finish(true);
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

  const startListening = useCallback(async () => {
    if (statusRef.current !== 'idle') return;
    if (!socketReady()) { setError(ERR_SERVER); return; }
    if (!navigator.mediaDevices?.getUserMedia) { setError(ERR_NO_MIC_API); return; }

    setError('');
    stopSpeaking();

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setError(ERR_MIC_DENIED);
      return;
    }

    const mime = pickMime();
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    const ctx = new AudioContext();
    ctx.resume?.();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    analyserRef.current = analyser;

    const samples = new Float32Array(analyser.fftSize);
    const startedAt = performance.now();
    let lastVoice = startedAt;
    let heardSpeech = false;
    let cancelled = false;
    let timer;

    const finish = (cancel = false) => {
      cancelled = cancel;
      clearInterval(timer);
      if (rec.state !== 'inactive') rec.stop();
    };

    // Détection du silence : volume (RMS) mesuré toutes les 50 ms
    timer = setInterval(() => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
      const now = performance.now();
      if (Math.sqrt(sum / samples.length) > SPEECH_RMS) { heardSpeech = true; lastVoice = now; }
      if (heardSpeech && now - lastVoice > SILENCE_MS) finish();
      else if (!heardSpeech && now - startedAt > NO_SPEECH_MS) finish();
      else if (now - startedAt > MAX_RECORD_MS) finish();
    }, 50);

    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
      analyserRef.current = null;
      sessionRef.current = null;

      if (cancelled) { setStatus('idle'); return; }
      if (!heardSpeech) {
        setStatus('idle');
        add(mk('notice', "Je n'ai rien entendu. Appuie sur le micro et parle dès que « J'écoute… » s'affiche."));
        return;
      }
      if (!socketReady()) { setStatus('idle'); setError(ERR_SERVER); return; }
      setStatus('thinking');
      wsRef.current.send(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }));
      armReplyTimeout();
    };

    sessionRef.current = { finish };
    rec.start();
    setStatus('listening');
  }, [add, armReplyTimeout, stopSpeaking]);

  const toggleListening = useCallback(() => {
    if (statusRef.current === 'listening') sessionRef.current?.finish();
    else startListening();
  }, [startListening]);

  const cancelListening = useCallback(() => sessionRef.current?.finish(true), []);
  const clearHistory = useCallback(() => setMessages([]), []);
  const dismissError = useCallback(() => setError(''), []);

  return {
    connected, status, messages, error, analyserRef,
    sendText, toggleListening, cancelListening, clearHistory, dismissError,
  };
}