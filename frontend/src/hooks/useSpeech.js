import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const LS_VOICE = 'va.voice';
const LS_ENABLED = 'va.tts';
const CHARS_PER_SEC = 14;   // estimation du débit quand la voix ne signale pas les mots (événement boundary absent)
const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } };

/**
 * Synthèse vocale du navigateur (speechSynthesis) : aucune installation côté Python.
 * `progress` = { id, char } : quel message est lu et jusqu'à quel caractère, pour surligner les mots (karaoké).
 * Les voix locales de Windows signalent chaque mot (boundary) ; pour les autres, la position est estimée au temps.
 */
export function useSpeech(locale) {
  const [allVoices, setAllVoices] = useState([]);
  const [voiceURI, setVoiceURI] = useState(() => read(LS_VOICE) || '');
  const [enabled, setEnabled] = useState(() => read(LS_ENABLED) !== 'off');
  const [speaking, setSpeaking] = useState(false);
  const [progress, setProgress] = useState({ id: null, char: -1 });
  const tickRef = useRef(null);
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  useEffect(() => {
    if (!supported) return undefined;
    const load = () => setAllVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener('voiceschanged', load);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load);
  }, [supported]);

  const voices = useMemo(() => {
    const prefix = locale.slice(0, 2).toLowerCase();
    return allVoices.filter((v) => v.lang.toLowerCase().startsWith(prefix));
  }, [allVoices, locale]);

  const voice = useMemo(
    () => voices.find((v) => v.voiceURI === voiceURI) || voices.find((v) => v.localService) || voices[0],
    [voices, voiceURI],
  );

  const finish = useCallback(() => {
    clearInterval(tickRef.current);
    setSpeaking(false);
    setProgress({ id: null, char: -1 });
  }, []);

  useEffect(() => () => clearInterval(tickRef.current), []);

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    finish();
  }, [supported, finish]);

  const speak = useCallback((text, id = null) => {
    if (!supported || !enabled || !text) return;
    window.speechSynthesis.cancel();
    clearInterval(tickRef.current);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = voice?.lang || locale;
    if (voice) u.voice = voice;
    let exact = false;
    u.onstart = () => {
      setSpeaking(true);
      setProgress({ id, char: 0 });
      const started = performance.now();
      tickRef.current = setInterval(() => {
        if (exact) return;
        const char = Math.min(text.length, Math.round(((performance.now() - started) / 1000) * CHARS_PER_SEC));
        setProgress({ id, char });
      }, 120);
    };
    u.onboundary = (e) => {
      if (e.name && e.name !== 'word') return;
      exact = true;
      setProgress({ id, char: e.charIndex });
    };
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
  }, [supported, enabled, voice, locale, finish]);

  const toggle = useCallback(() => {
    setEnabled((on) => {
      write(LS_ENABLED, on ? 'off' : 'on');
      if (on) stop();
      return !on;
    });
  }, [stop]);

  const chooseVoice = useCallback((uri) => { setVoiceURI(uri); write(LS_VOICE, uri); }, []);

  return { supported, speak, stop, speaking, progress, enabled, toggle, voices, voice, chooseVoice };
}
