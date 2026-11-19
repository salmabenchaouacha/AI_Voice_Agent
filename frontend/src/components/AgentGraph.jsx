/**
 * Schéma du graphe LangGraph de l'agent, animé en direct.
 *
 *   Réflexion ──► Validation ──► Outils
 *       ▲                          │
 *       └──────────────────────────┘
 *
 * `node` vient du serveur pendant la demande : "agent", "review", "tools", ou "waiting" (pause de confirmation).
 */
const NODES = [
  { id: 'agent', label: 'Réflexion', x: 8 },
  { id: 'review', label: 'Validation', x: 128 },
  { id: 'tools', label: 'Outils', x: 248 },
];
const W = 104;
const H = 34;
const Y = 8;

const CAPTIONS = {
  agent: 'Le modèle réfléchit',
  review: 'Le garde-fou vérifie les actions',
  tools: 'Exécution des outils',
  waiting: 'En attente de ta confirmation',
};

export default function AgentGraph({ node }) {
  const active = node === 'waiting' ? 'review' : node;
  return (
    <figure className="graph" data-node={node || 'idle'}>
      <svg viewBox="0 0 360 74" role="img" aria-label={`Graphe de l'agent : ${CAPTIONS[node] || 'au repos'}`}>
        <defs>
          <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" className="graph-arrowhead" />
          </marker>
        </defs>
        <line x1={8 + W} y1={Y + H / 2} x2={128 - 2} y2={Y + H / 2} className="graph-edge" markerEnd="url(#arrow)" />
        <line x1={128 + W} y1={Y + H / 2} x2={248 - 2} y2={Y + H / 2} className="graph-edge" markerEnd="url(#arrow)" />
        <path d={`M${248 + W / 2},${Y + H} V66 H${8 + W / 2} V${Y + H + 2}`} className="graph-edge graph-loop"
          markerEnd="url(#arrow)" />
        {NODES.map((n) => (
          <g key={n.id} className="graph-node" data-active={active === n.id}
            data-waiting={node === 'waiting' && n.id === 'review'}>
            <rect x={n.x} y={Y} width={W} height={H} rx="9" />
            <text x={n.x + W / 2} y={Y + H / 2 + 5} textAnchor="middle">{n.label}</text>
          </g>
        ))}
      </svg>
      <figcaption>{CAPTIONS[node] || 'Graphe de l\'agent'}</figcaption>
    </figure>
  );
}
