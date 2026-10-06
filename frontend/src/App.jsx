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

// Proposées seulement quand l'agent est actif : plusieurs actions, mémoire, recherche lue, confirmation.
const SUGGESTIONS_AGENT = [
  'Quelle heure est-il ?',
  'Météo à Sousse puis minuteur de 10 minutes',
  'Note de réviser le RAG et relis mes notes',
  'Cherche les nouveautés de LangGraph',
  "Je m'appelle Salma, retiens-le",
  "Verrouille l'écran",
];

const STATUS = {
  idle: 'Appuie sur le micro et parle',
  listening: "J'écoute…",
  thinking: 'Je réfléchis…',
  speaking: 'Je parle…',
};

const MODES = { agent: 'Agent IA', offline: 'Mode hors-ligne' };
const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export default function App() {
  const [lang, setLang] = useState('fr');
  const [mode, setMode] = useState('');
  const locale = LOCALES[lang] || 'fr-FR';

  const speech = useSpeech(locale);
  const a = useAssistant({ speak: speech.speak, stopSpeaking: speech.stop });

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((c) => c.language && setLang(c.language))
      .catch(() => {});
    fetch('/api/status')
      .then((r) => r.json())
      .then((s) => MODES[s.mode] && setMode(s.mode))
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
  const statusText = phase === 'thinking' && a.activity ? `${capitalize(a.activity)}…` : STATUS[phase];

  return (
    <div className="app">
      <main className="stage">
        <header className="bar">
          <h1 className="brand">
            Assistant vocal
            {mode && <span className="mode" data-mode={mode}>{MODES[mode]}</span>}
          </h1>
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
          <p className="status" aria-live="polite">{a.connected ? statusText : 'Serveur injoignable'}</p>
          {a.pending && a.connected ? (
            <div className="confirm" role="group" aria-label="Confirmer l'action">
              <button type="button" className="yes" disabled={busy} onClick={() => a.sendText('oui')}>Oui</button>
              <button type="button" className="no" disabled={busy} onClick={() => a.sendText('non')}>Non</button>
              <p className="hint">Réponds oui ou non, à la voix ou avec ces boutons</p>
            </div>
          ) : (
            <p className="hint">Espace pour parler ou arrêter, Échap pour annuler</p>
          )}

          {a.error && (
            <p className="error" role="alert">
              {a.error}
              <button type="button" className="linkbtn" onClick={a.dismissError}>Fermer</button>
            </p>
          )}

          <div className="chips">
            {(mode === 'agent' ? SUGGESTIONS_AGENT : SUGGESTIONS).map((s) => (
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