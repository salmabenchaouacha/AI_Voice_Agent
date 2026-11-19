import { useEffect, useRef } from 'react';
import Cards from './Cards.jsx';
import { HeardWords, Karaoke, UNSURE } from './Spoken.jsx';
import Trace from './Trace.jsx';

export default function History({ messages, locale, onClear, draft = '', speaking = { id: null, char: -1 } }) {
  const box = useRef(null);

  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [messages, draft]);

  const charFor = (m) => (speaking?.id === m.id ? speaking.char : -1);

  const time = (iso) => new Date(iso).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });

  return (
    <section className="log" aria-label="Conversation">
      <header className="log-head">
        <h2>Conversation</h2>
        {messages.length > 0 && (
          <button type="button" className="linkbtn" onClick={onClear}>Effacer l'historique</button>
        )}
      </header>

      <div className="log-scroll" ref={box} role="log" aria-live="polite">
        {messages.length === 0 && (
          <p className="empty">
            Rien pour l'instant. Appuie sur le micro et dis par exemple « quel temps fait-il à Sousse ? »,
            ou touche une suggestion.
          </p>
        )}
        {messages.map((m) => (
          <article key={m.id} className="msg" data-role={m.role}>
            {m.role === 'notice' ? (
              <p className="notice"><Karaoke text={m.text} char={charFor(m)} /></p>
            ) : (
              <>
                <div className="meta">
                  <span className={m.role === 'user' ? 'who-you' : 'who-bot'}>
                    {m.role === 'user' ? (m.via === 'voice' ? 'Vous (voix)' : 'Vous') : 'Assistant'}
                  </span>
                  <time dateTime={m.time}>{time(m.time)}</time>
                </div>
                {m.role === 'user' ? (
                  <p className="you">{m.words?.length ? <HeardWords words={m.words} /> : m.text}</p>
                ) : (
                  <p className="bot" data-speaking={charFor(m) >= 0}><Karaoke text={m.text} char={charFor(m)} /></p>
                )}
                {m.role === 'user' && m.words?.some((w) => w.p < UNSURE) && (
                  <p className="unsure-hint">Mots soulignés : Whisper n'en était pas sûr.</p>
                )}
                {m.tools?.length > 0 && (
                  <p className="tools" aria-label="Outils utilisés">
                    {m.tools.map((t, i) => <span key={`${t}-${i}`} className="tool">{t}</span>)}
                  </p>
                )}
                {m.role === 'assistant' && <Cards cards={m.cards} />}
                {m.role === 'assistant' && <Trace steps={m.trace} />}
              </>
            )}
          </article>
        ))}
        {draft && (
          <article className="msg" data-role="assistant" data-streaming="true">
            <div className="meta"><span className="who-bot">Assistant</span></div>
            <p className="bot">{draft}<span className="caret" aria-hidden="true" /></p>
          </article>
        )}
      </div>
    </section>
  );
}