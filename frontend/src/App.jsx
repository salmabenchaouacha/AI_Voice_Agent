import { useEffect, useState } from 'react';
import Composer from './components/Composer.jsx';
import History from './components/History.jsx';
import MicButton from './components/MicButton.jsx';
import { useAssistant } from './hooks/useAssistant.js';
import { useSpeech } from './hooks/useSpeech.js';

const LOCALES = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' };

const SUGGESTIONS = [
  'Quelle heure est-il ?',
  'Quel temps fait-il à Sousse ?',
  'Ouvre YouTube',
  'Minuteur de 5 minutes',
  'Prends une note : réviser le cours de RAG',
  'Raconte-moi une blague',
];

const STATUS = {
  idle: 'Appuie sur le micro et parle',
  listening: "J'écoute…",
  thinking: 'Je réfléchis…',
  speaking: 'Je parle…',
};

export default function App() {
  const [lang, setLang] = useState('fr');
  const locale = LOCALES[lang] || 'fr-FR';

  const speech = useSpeech(locale);
  const a = useAssistant({ speak: speech.speak, stopSpeaking: speech.stop });

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((c) => c.language && setLang(c.language))
      .catch(() => {});
  }, []);

  const phase = a.status === 'idle' && speech.speaking ? 'speaking' : a.status;

  const onMicClick = () => {
    if (phase === 'speaking') speech.stop();
    else a.toggleListening();
  };

  // Raccourcis : Espace = parler / arrêter, Échap = annuler
  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(e.target.tagName)) return;
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        if (speech.speaking) speech.stop();
        else a.toggleListening();
      } else if (e.key === 'Escape') {
        a.cancelListening();
        speech.stop();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [a.toggleListening, a.cancelListening, speech.speaking, speech.stop]); // eslint-disable-line react-hooks/exhaustive-deps

  const busy = a.status !== 'idle';

  return (
    <div className="app">
      <main className="stage">
        <header className="bar">
          <h1 className="brand">Assistant vocal</h1>
          <span className="conn" data-ok={a.connected}>
            <span className="dot" aria-hidden="true" />
            {a.connected ? 'Connecté au serveur' : 'Serveur injoignable, reconnexion…'}
          </span>
        </header>

        <div className="stage-main">
          <MicButton
            phase={phase}
            analyserRef={a.analyserRef}
            disabled={!a.connected || phase === 'thinking'}
            onClick={onMicClick}
          />
          <p className="status" aria-live="polite">{a.connected ? STATUS[phase] : 'Serveur injoignable'}</p>
          <p className="hint">Espace pour parler ou arrêter, Échap pour annuler</p>

          {a.error && (
            <p className="error" role="alert">
              {a.error}
              <button type="button" className="linkbtn" onClick={a.dismissError}>Fermer</button>
            </p>
          )}

          <div className="chips">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" disabled={!a.connected || busy} onClick={() => a.sendText(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {speech.supported && (
          <footer className="voice">
            <button type="button" role="switch" aria-checked={speech.enabled} className="switch" onClick={speech.toggle}>
              <span className="track" aria-hidden="true" />
              Réponses vocales
            </button>
            {speech.voices.length > 1 && (
              <select
                aria-label="Voix de l'assistant"
                value={speech.voice?.voiceURI || ''}
                onChange={(e) => speech.chooseVoice(e.target.value)}
              >
                {speech.voices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>{v.name}</option>
                ))}
              </select>
            )}
          </footer>
        )}
      </main>

      <aside className="side">
        <History messages={a.messages} locale={locale} onClear={a.clearHistory} />
        <Composer disabled={!a.connected || busy} onSend={a.sendText} />
      </aside>
    </div>
  );
}