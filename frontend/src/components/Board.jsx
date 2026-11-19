import { useEffect, useState } from 'react';

const pad = (n) => String(n).padStart(2, '0');

/** 125000 ms -> « 02:05 », 3725000 ms -> « 1:02:05 » */
export function formatRemaining(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
}

/** Jour d'un rappel : « » aujourd'hui, « demain », ou « ven. 21/11 ». */
export function reminderDay(at, serverNow) {
  const d = new Date(at);
  if (d.toDateString() === new Date(serverNow).toDateString()) return '';
  if (d.toDateString() === new Date(serverNow + 86400000).toDateString()) return 'demain';
  return d.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' });
}

/** « dans 2 h 05 », « dans 12 min », « dans 3 j », « dans moins d'une minute » */
export function formatIn(ms) {
  const min = Math.floor(ms / 60000);
  if (min < 1) return "dans moins d'une minute";
  if (min < 60) return `dans ${min} min`;
  if (min < 2880) return `dans ${Math.floor(min / 60)} h ${pad(min % 60)}`;
  return `dans ${Math.round(min / 1440)} j`;
}

const clockOf = (at) => { const d = new Date(at); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };

/**
 * Panneau de droite : ce que l'agent a lancé, noté ou programmé reste visible à l'écran.
 * Le serveur envoie l'heure de fin de chaque minuteur ; le décompte se fait ici, sans requête.
 * `offset` corrige un éventuel écart entre l'horloge du serveur et celle du navigateur.
 */
const OUTCOMES = { confirmée: 'ok', refusée: 'no', remplacée: 'warn' };
const clock = (t) => new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

export default function Board({ timers, notes, tasks = [], reminders = [], audit = [], offset = 0, onToggleTask }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!timers.length && !reminders.length) return undefined;
    setNow(Date.now());
    const tick = setInterval(() => setNow(Date.now()), timers.length ? 250 : 15000);
    return () => clearInterval(tick);
  }, [timers, reminders]);

  const serverNow = now + offset;
  const running = timers
    .map((t) => ({ ...t, left: t.end - serverNow }))
    .filter((t) => t.left > 0);

  const upcoming = reminders.filter((r) => r.at > serverNow - 60000);

  if (!running.length && !notes.length && !audit.length && !tasks.length && !upcoming.length) return null;

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
      {upcoming.length > 0 && (
        <div className="board-block">
          <h2>Rappels</h2>
          <ul className="reminders">
            {upcoming.map((r) => (
              <li key={r.id} className="reminder">
                <span className="reminder-time">{clockOf(r.at)}</span>
                <span className="reminder-text">{r.text}</span>
                <span className="reminder-in">
                  {[reminderDay(r.at, serverNow), formatIn(r.at - serverNow)].filter(Boolean).join(' · ')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {tasks.length > 0 && (
        <div className="board-block">
          <h2>Tâches <span className="board-count">{tasks.filter((t) => !t.done).length} à faire</span></h2>
          <ul className="tasks">
            {tasks.map((t) => (
              <li key={t.id} className="task" data-done={t.done}>
                <label>
                  <input type="checkbox" checked={t.done} disabled={!onToggleTask}
                    onChange={() => onToggleTask?.(t.id)} />
                  <span className="task-text">{t.text}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
      {audit.length > 0 && (
        <div className="board-block">
          <h2>Actions sensibles</h2>
          <ul className="audit">
            {audit.map((e, i) => (
              <li key={`${e.t}-${i}`} className="audit-item">
                <span className="audit-action">{e.action}</span>
                <span className="audit-outcome" data-outcome={OUTCOMES[e.outcome] || 'warn'}>{e.outcome}</span>
                <span className="audit-meta">{e.t ? clock(e.t) : ''} · {e.reason}</span>
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
