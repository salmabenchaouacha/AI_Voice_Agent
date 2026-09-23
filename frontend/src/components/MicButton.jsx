import { useEffect, useRef } from 'react';

const SIZE = 320;      // repère de dessin (le CSS met le canvas à l'échelle)
const BARS = 72;
const INNER = 96;      // rayon intérieur des barres (le bouton fait 78)

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

/** Bouton micro entouré d'un anneau de barres animé par le son réel du micro. */
export default function MicButton({ phase, analyserRef, disabled, onClick }) {
  const canvasRef = useRef(null);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    ctx.scale(dpr, dpr);

    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const levels = new Float32Array(BARS);
    const freq = new Uint8Array(256);
    const t0 = performance.now();
    let raf;

    const draw = (now) => {
      const t = (now - t0) / 1000;
      const p = phaseRef.current;
      const analyser = analyserRef.current;
      if (p === 'listening' && analyser) analyser.getByteFrequencyData(freq);

      const css = getComputedStyle(canvas);
      ctx.clearRect(0, 0, SIZE, SIZE);
      ctx.strokeStyle = css.getPropertyValue(p === 'listening' ? '--rec' : p === 'thinking' ? '--wait' : '--signal').trim();
      ctx.lineWidth = 4;
      ctx.lineCap = 'round';

      for (let i = 0; i < BARS; i += 1) {
        let target;
        if (p === 'listening' && analyser) {
          // spectre symétrique : les graves au bas de l'anneau, les aigus en haut
          const bin = 1 + Math.floor((Math.abs(i - BARS / 2) / (BARS / 2)) * 44);
          target = (freq[bin] / 255) ** 1.3;
        } else if (p === 'speaking') {
          target = calm ? 0.25 : 0.18 + 0.22 * Math.abs(Math.sin(t * 5 + i * 0.45) * Math.sin(t * 1.7 + i * 0.13));
        } else if (p === 'thinking') {
          target = calm ? 0.2 : 0.08 + 0.4 * Math.max(0, Math.cos((i / BARS) * Math.PI * 2 - t * 4)) ** 4;
        } else {
          target = calm ? 0.05 : 0.05 + 0.03 * Math.sin(t * 1.2 + i * 0.35);
        }
        levels[i] += (target - levels[i]) * 0.3;

        const a = (i / BARS) * Math.PI * 2 - Math.PI / 2;
        const len = 4 + levels[i] * 58;
        ctx.beginPath();
        ctx.moveTo(SIZE / 2 + Math.cos(a) * INNER, SIZE / 2 + Math.sin(a) * INNER);
        ctx.lineTo(SIZE / 2 + Math.cos(a) * (INNER + len), SIZE / 2 + Math.sin(a) * (INNER + len));
        ctx.stroke();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [analyserRef]);

  return (
    <div className="orb">
      <canvas ref={canvasRef} aria-hidden="true" />
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