/**
 * Texte avec surlignage :
 *  - Karaoke : les mots déjà dits par la synthèse vocale (char = position lue, -1 = pas en lecture).
 *  - HeardWords : ce que Whisper a entendu, mots incertains soulignés avec leur probabilité.
 */
export const UNSURE = 0.6;   // en dessous, le mot est signalé comme incertain

export function Karaoke({ text, char = -1 }) {
  if (char < 0) return text;
  let offset = 0;
  return text.split(/(\s+)/).map((part, i) => {
    const start = offset;
    offset += part.length;
    if (!part.trim()) return part;
    const state = start + part.length <= char ? 'said' : start <= char ? 'now' : 'todo';
    return <span key={i} className="kw" data-state={state}>{part}</span>;
  });
}

export function HeardWords({ words }) {
  return words.map((w, i) => {
    const sep = i ? ' ' : '';
    if (w.p >= UNSURE) return sep + w.w;
    return (
      <span key={i}>
        {sep}
        <mark className="unsure" title={`Whisper n'est pas sûr de ce mot (${Math.round(w.p * 100)} %)`}>{w.w}</mark>
      </span>
    );
  });
}
