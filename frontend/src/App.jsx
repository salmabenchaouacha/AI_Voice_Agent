import { useEffect, useState } from 'react';
import Composer from './components/Composer.jsx';
import History from './components/History.jsx';
import { useAssistant } from './hooks/useAssistant.js';

const LOCALES = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' };

const SUGGESTIONS = [
  'Quelle heure est-il ?',
  'Quel temps fait-il à Sousse ?',
  'Ouvre YouTube',
  'Minuteur de 5 minutes',
  'Prends une note : réviser le cours de RAG',
  'Raconte-moi une blague',
];

const noop = () => {};

export default function App() {
  const [lang, setLang] = useState('fr');
  const locale = LOCALES[lang] || 'fr-FR';
  const a = useAssistant({ speak: noop, stopSpeaking: noop });

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((c) => c.language && setLang(c.language))
      .catch(() => {});
  }, []);

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
      </main>

      <aside className="side">
        <History messages={a.messages} locale={locale} onClear={a.clearHistory} />
        <Composer disabled={!a.connected || busy} onSend={a.sendText} />
      </aside>
    </div>
  );
}