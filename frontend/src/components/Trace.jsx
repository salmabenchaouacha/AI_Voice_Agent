/** Les étapes d'une demande, sous la réponse : réflexion du modèle, validation, outils, avec leur durée. */
export function formatMs(ms) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1).replace('.', ',')} s`;
}

function describe(step) {
  if (step.kind === 'llm') {
    const then = step.calls?.length ? ` → ${step.calls.join(', ')}` : ' → réponse';
    return { name: 'Réflexion', detail: `${formatMs(step.ms)}${then}`, tone: step.error ? 'error' : '' };
  }
  if (step.kind === 'review') {
    return {
      name: 'Validation',
      detail: step.items.map((i) => `${i.label} : ${i.outcome}`).join(', '),
      tone: step.items.some((i) => i.outcome !== 'confirmée') ? 'warn' : 'ok',
    };
  }
  const detail = step.status === 'ok' ? formatMs(step.ms) : step.status;
  return { name: step.label, detail, tone: step.status === 'ok' ? '' : step.status === 'refusé' ? 'warn' : 'error' };
}

export default function Trace({ steps }) {
  if (!steps?.length) return null;
  const total = steps.reduce((sum, s) => sum + (s.ms || 0), 0);
  return (
    <details className="trace">
      <summary>{steps.length} étape{steps.length > 1 ? 's' : ''} · {formatMs(total)}</summary>
      <ol>
        {steps.map((s, i) => {
          const d = describe(s);
          return (
            <li key={i} data-kind={s.kind} data-tone={d.tone}>
              <span className="trace-name">{d.name}</span>
              <span className="trace-detail">{d.detail}</span>
            </li>
          );
        })}
      </ol>
    </details>
  );
}
