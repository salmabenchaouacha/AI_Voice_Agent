/**
 * Cartes visuelles affichées sous une réponse de l'assistant.
 * Le serveur les envoie dans `cards` (voir backend/cards.py) : ce que l'assistant MONTRE en plus de ce qu'il DIT.
 *   weather  météo actuelle + prévisions, avec la carte de la ville
 *   sources  résultats d'une recherche web, cliquables
 *   map      carte OpenStreetMap centrée sur un lieu
 *   image    miniature d'une capture d'écran
 *   agenda   événements Google Agenda d'un jour (ou celui qui vient d'être ajouté)
 */
const DAYS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.'];

// Codes météo WMO (open-meteo) -> famille d'icône
function family(code) {
  if (code === 0) return 'sun';
  if (code === 1 || code === 2) return 'partly';
  if (code === 3) return 'cloud';
  if (code === 45 || code === 48) return 'fog';
  if ([71, 73, 75, 77, 85, 86].includes(code)) return 'snow';
  if ([95, 96, 99].includes(code)) return 'storm';
  if (code >= 51 && code <= 82) return 'rain';
  return 'cloud';
}

const CLOUD = 'M7 18h10a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.6A3.2 3.2 0 0 0 7 18z';

export function WeatherIcon({ code, size = 28 }) {
  const f = family(code);
  return (
    <svg className="wx-icon" data-family={f} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"
      fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      {f === 'sun' && (
        <g className="wx-sun">
          <circle cx="12" cy="12" r="4.2" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1="12" y1="2.5" x2="12" y2="4.6" transform={`rotate(${a} 12 12)`} />
          ))}
        </g>
      )}
      {f === 'partly' && (
        <>
          <g className="wx-sun"><circle cx="8.5" cy="8.5" r="3.2" /><line x1="8.5" y1="2.6" x2="8.5" y2="3.8" /><line x1="2.6" y1="8.5" x2="3.8" y2="8.5" /><line x1="4.3" y1="4.3" x2="5.2" y2="5.2" /></g>
          <path d={CLOUD} transform="translate(2 1.5) scale(0.88)" className="wx-cloud" />
        </>
      )}
      {f !== 'sun' && f !== 'partly' && <path d={CLOUD} transform="translate(0 -2.5)" className="wx-cloud" />}
      {f === 'rain' && <g className="wx-drop"><line x1="9" y1="18" x2="8" y2="21" /><line x1="13" y1="18" x2="12" y2="21" /><line x1="17" y1="18" x2="16" y2="21" /></g>}
      {f === 'snow' && <g className="wx-drop"><circle cx="9" cy="19.5" r="0.6" /><circle cx="13" cy="20.5" r="0.6" /><circle cx="17" cy="19.5" r="0.6" /></g>}
      {f === 'storm' && <path className="wx-bolt" d="M13 16l-2.5 3.5h3L11 23" />}
      {f === 'fog' && <g><line x1="5" y1="19" x2="19" y2="19" /><line x1="7" y1="21.5" x2="17" y2="21.5" /></g>}
    </svg>
  );
}

function dayLabel(iso, index) {
  if (index === 0) return "Auj.";
  if (index === 1) return 'Demain';
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : DAYS[d.getDay()];
}

function osm(lat, lon, zoom = 0.06) {
  const bbox = [lon - zoom, lat - zoom * 0.6, lon + zoom, lat + zoom * 0.6].map((n) => n.toFixed(4)).join(',');
  return {
    embed: `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`,
    link: `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=12/${lat}/${lon}`,
  };
}

function MapFrame({ lat, lon, title, zoom }) {
  if (typeof lat !== 'number' || typeof lon !== 'number') return null;
  const { embed, link } = osm(lat, lon, zoom);
  return (
    <div className="map">
      <iframe title={`Carte : ${title}`} src={embed} loading="lazy" referrerPolicy="no-referrer" />
      <a href={link} target="_blank" rel="noreferrer">Ouvrir dans OpenStreetMap</a>
    </div>
  );
}

function WeatherCard({ card }) {
  const days = Array.isArray(card.days) ? card.days.slice(0, 4) : [];
  return (
    <section className="card card-weather" aria-label={`Météo à ${card.city}`}>
      <div className="wx-now">
        <WeatherIcon code={card.code} size={44} />
        <div className="wx-main">
          <span className="wx-temp">{card.temp}°</span>
          <span className="wx-city">{card.city}{card.country ? `, ${card.country}` : ''}</span>
        </div>
        <div className="wx-side">
          {card.sky && <span>{card.sky.charAt(0).toUpperCase() + card.sky.slice(1)}</span>}
          {typeof card.wind === 'number' && <span>Vent {card.wind} km/h</span>}
        </div>
      </div>
      {days.length > 1 && (
        <ol className="wx-days">
          {days.map((d, i) => (
            <li key={d.date} title={d.sky}>
              <span className="wx-day">{dayLabel(d.date, i)}</span>
              <WeatherIcon code={d.code} size={22} />
              <span className="wx-range"><b>{d.max}°</b> {d.min}°</span>
            </li>
          ))}
        </ol>
      )}
      {typeof card.lat === 'number' && (
        <details className="card-more">
          <summary>Voir sur la carte</summary>
          <MapFrame lat={card.lat} lon={card.lon} title={card.city} zoom={0.12} />
        </details>
      )}
    </section>
  );
}

function SourcesCard({ card }) {
  const items = Array.isArray(card.items) ? card.items.filter((it) => /^https?:\/\//.test(it.url || '')) : [];
  if (!items.length) return null;
  return (
    <section className="card card-sources" aria-label="Sources de la recherche">
      <h3>Sources{card.query ? ` · ${card.query}` : ''}</h3>
      <ol>
        {items.map((it, i) => (
          <li key={`${it.url}-${i}`}>
            <a href={it.url} target="_blank" rel="noreferrer">
              <span className="src-site">{it.site}</span>
              <span className="src-title">{it.title}</span>
              {it.snippet && <span className="src-snippet">{it.snippet}</span>}
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}

function MapCard({ card }) {
  return (
    <section className="card card-map" aria-label={`Carte : ${card.name}`}>
      <h3>{card.name}{card.place ? <span> · {card.place}</span> : null}</h3>
      <MapFrame lat={card.lat} lon={card.lon} title={card.name} />
    </section>
  );
}

function ImageCard({ card }) {
  // Seulement les images servies par notre propre serveur (captures d'écran)
  if (!/^\/api\/captures\/[\w.-]+$/.test(card.url || '')) return null;
  return (
    <section className="card card-image" aria-label={card.title || 'Image'}>
      <a href={card.url} target="_blank" rel="noreferrer">
        <img src={card.url} alt={card.title || 'Capture d\'écran'} loading="lazy" />
      </a>
      {card.title && <p>{card.title}</p>}
    </section>
  );
}

function AgendaCard({ card }) {
  const events = Array.isArray(card.events) ? card.events : [];
  return (
    <section className="card card-agenda" aria-label={`Agenda : ${card.title}`}>
      <h3>{card.added ? 'Ajouté à l\'agenda' : 'Agenda'}<span> · {card.title}</span></h3>
      {events.length === 0 ? (
        <p className="agenda-empty">Rien de prévu.</p>
      ) : (
        <ol>
          {events.map((ev, i) => (
            <li key={`${ev.time}-${i}`} data-added={!!card.added}>
              <span className="agenda-time">{ev.allDay ? 'Journée' : ev.time}</span>
              <span className="agenda-title">{ev.title}</span>
              {!ev.allDay && ev.end && <span className="agenda-end">jusqu'à {ev.end}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const KINDS = { weather: WeatherCard, sources: SourcesCard, map: MapCard, image: ImageCard, agenda: AgendaCard };

export default function Cards({ cards }) {
  const list = Array.isArray(cards) ? cards.filter((c) => c && KINDS[c.kind]) : [];
  if (!list.length) return null;
  return (
    <div className="cards">
      {list.map((c, i) => {
        const Card = KINDS[c.kind];
        return <Card key={`${c.kind}-${i}`} card={c} />;
      })}
    </div>
  );
}
