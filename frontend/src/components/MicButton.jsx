function Icon({ phase }) {
  if (phase === 'listening') {
    return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2.5" /></svg>;
  }
  if (phase === 'speaking') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M5 9v6M9 6v12M13 8v8M17 10v4M21 11.5v1" />
      </svg>
    );
  }
  if (phase === 'thinking') {
    return (
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}

const LABELS = {
  idle: 'Parler',
  listening: "Arrêter l'enregistrement",
  thinking: 'Traitement en cours',
  speaking: 'Arrêter la voix',
};

/** Bouton micro : un seul bouton, quatre états (parler, écoute, traitement, voix). */
export default function MicButton({ phase, disabled, onClick }) {
  return (
    <div className="orb">
      <button
        type="button"
        className="orb-btn"
        data-phase={phase}
        disabled={disabled}
        aria-label={LABELS[phase]}
        onClick={onClick}
      >
        <Icon phase={phase} />
      </button>
    </div>
  );
}