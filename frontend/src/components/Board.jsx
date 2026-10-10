import { useEffect, useState } from 'react';

const pad = (n) => String(n).padStart(2, '0');

/** 125000 ms -> « 02:05 », 3725000 ms -> « 1:02:05 » */
export function formatRemaining(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
}

/**
 * Panneau « Minuteurs et notes » : ce que l'agent a lancé ou noté reste visible à l'écran.
 * Le serveur envoie l'heure de fin de chaque minuteur ; le décompte se fait ici, sans requête.
 * `offset` corrige un éventuel écart entre l'horloge du serveur et celle du navigateur.
 */
export default function Board({ timers, notes, offset = 0 }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!timers.length) return undefined;
    setNow(Date.now());
    const tick = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(tick);
  }, [timers]);

  const serverNow = now + offset;
  const running = timers
    .map((t) => ({ ...t, left: t.end - serverNow }))
    .filter((t) => t.left > 0);

  if (!running.length && !notes.length) return null;

  return (
    <section className="board" aria-label="Minuteurs et notes">
      {running.length > 0 && (
        <div className="board-block">
          <h2>Minuteurs</h2>
          <ul className="timers">
            {running.map((t) => (
              <li key={t.id} className="timer">
                <span className="timer-label">{t.label || 'Minuteur'}</span>
                <span className="timer-time" aria-label={`Temps restant ${t.label || ''}`.trim()}>
                  {formatRemaining(t.left)}
                </span>
                <span className="timer-bar" aria-hidden="true">
                  <span style={{ width: `${Math.min(100, (100 * t.left) / (t.seconds * 1000))}%` }} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {notes.length > 0 && (
        <div className="board-block">
          <h2>Notes</h2>
          <ul className="notes">
            {notes.map((n, i) => (
              <li key={`${n.date}-${n.time}-${i}`} className="note">
                <span className="note-text">{n.text}</span>
                {n.time && <time className="note-time">{n.time}</time>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}