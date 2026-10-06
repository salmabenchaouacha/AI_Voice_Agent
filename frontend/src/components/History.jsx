import { useEffect, useRef } from 'react';

export default function History({ messages, locale, onClear }) {
  const box = useRef(null);

  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [messages]);

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
              <p className="notice">{m.text}</p>
            ) : (
              <>
                <div className="meta">
                  <span className={m.role === 'user' ? 'who-you' : 'who-bot'}>
                    {m.role === 'user' ? (m.via === 'voice' ? 'Vous (voix)' : 'Vous') : 'Assistant'}
                  </span>
                  <time dateTime={m.time}>{time(m.time)}</time>
                </div>
                <p className={m.role === 'user' ? 'you' : 'bot'}>{m.text}</p>
                {m.tools?.length > 0 && (
                  <p className="tools" aria-label="Outils utilisés">
                    {m.tools.map((t, i) => <span key={`${t}-${i}`} className="tool">{t}</span>)}
                  </p>
                )}
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}