import { useCallback, useEffect, useMemo, useState } from 'react';

const LS_VOICE = 'va.voice';
const LS_ENABLED = 'va.tts';
const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } };

/** Synthèse vocale du navigateur (speechSynthesis) : aucune installation côté Python. */
export function useSpeech(locale) {
  const [allVoices, setAllVoices] = useState([]);
  const [voiceURI, setVoiceURI] = useState(() => read(LS_VOICE) || '');
  const [enabled, setEnabled] = useState(() => read(LS_ENABLED) !== 'off');
  const [speaking, setSpeaking] = useState(false);
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

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [supported]);

  const speak = useCallback((text) => {
    if (!supported || !enabled || !text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = voice?.lang || locale;
    if (voice) u.voice = voice;
    u.onstart = () => setSpeaking(true);
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
  }, [supported, enabled, voice, locale]);

  const toggle = useCallback(() => {
    setEnabled((on) => {
      write(LS_ENABLED, on ? 'off' : 'on');
      if (on) stop();
      return !on;
    });
  }, [stop]);

  const chooseVoice = useCallback((uri) => { setVoiceURI(uri); write(LS_VOICE, uri); }, []);

  return { supported, speak, stop, speaking, enabled, toggle, voices, voice, chooseVoice };
}
