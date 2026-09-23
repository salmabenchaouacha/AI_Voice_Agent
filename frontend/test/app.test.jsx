import { render, screen, act, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import App from '../src/App.jsx';

class FakeWS {
  static OPEN = 1;
  static instances = [];
  readyState = 0;
  sent = [];
  constructor(url) { this.url = url; FakeWS.instances.push(this); setTimeout(() => { this.readyState = 1; this.onopen?.(); }, 0); }
  send(d) { this.sent.push(d); }
  close() { this.readyState = 3; this.onclose?.(); }
  serverSays(obj) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

const spoken = [];
let loud = true;

beforeEach(() => {
  localStorage.clear();
  FakeWS.instances = [];
  spoken.length = 0;
  loud = true;
  global.WebSocket = FakeWS;
  global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ language: 'fr' }) }));
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  HTMLCanvasElement.prototype.getContext = () => ({ scale() {}, clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {} });
  window.speechSynthesis = {
    getVoices: () => [{ name: 'Hortense', lang: 'fr-FR', voiceURI: 'h', localService: true }, { name: 'Paul', lang: 'fr-FR', voiceURI: 'p', localService: true }],
    addEventListener() {}, removeEventListener() {}, cancel() {}, speak: (u) => spoken.push(u.text),
  };
  global.SpeechSynthesisUtterance = function (t) { this.text = t; };
  global.AudioContext = function () {
    this.resume = () => {}; this.close = () => {};
    this.createMediaStreamSource = () => ({ connect() {} });
    this.createAnalyser = () => ({ fftSize: 512, getFloatTimeDomainData: (a) => a.fill(loud ? 0.2 : 0), getByteFrequencyData() {} });
  };
  global.MediaRecorder = class {
    static isTypeSupported() { return true; }
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm'; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['abc']) }); this.onstop?.(); }
  };
  navigator.mediaDevices = { getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [{ stop() {} }] })) };
});
afterEach(cleanup);

const ws = () => FakeWS.instances.at(-1);
const connect = async () => { render(<App />); await waitFor(() => screen.getByText('Connecté au serveur')); };

describe('Assistant vocal', () => {
  it('se connecte et affiche la liste des voix', async () => {
    await connect();
    expect(screen.getByLabelText("Voix de l'assistant")).toBeTruthy();
  });

  it('commande texte : envoi, réponse affichée et parlée', async () => {
    await connect();
    fireEvent.click(screen.getByText('Quelle heure est-il ?'));
    expect(JSON.parse(ws().sent.at(-1))).toEqual({ type: 'text', text: 'Quelle heure est-il ?' });
    expect(screen.getByText('Je réfléchis…')).toBeTruthy();
    act(() => ws().serverSays({ type: 'result', source: 'text', heard: 'Quelle heure est-il ?', reply: 'Il est 14 heures 02.' }));
    expect(screen.getByText('Il est 14 heures 02.')).toBeTruthy();
    expect(spoken).toEqual(['Il est 14 heures 02.']);
    expect(screen.getAllByText('Quelle heure est-il ?').length).toBe(2); // chip + historique (pas de doublon)
    expect(JSON.parse(localStorage.getItem('va.history.v1')).length).toBe(2);
  });

  it('notification serveur (minuteur)', async () => {
    await connect();
    act(() => ws().serverSays({ type: 'notification', text: 'Ton minuteur est terminé !' }));
    expect(screen.getByText('Ton minuteur est terminé !')).toBeTruthy();
    expect(spoken).toContain('Ton minuteur est terminé !');
  });

  it('flux vocal : enregistrement, arrêt au silence, audio envoyé, transcription affichée', async () => {
    await connect();
    fireEvent.click(screen.getByLabelText('Parler'));
    await waitFor(() => screen.getByText("J'écoute…"));
    await new Promise((r) => setTimeout(r, 300));
    loud = false;                                            // la personne se tait
    await waitFor(() => expect(ws().sent.some((d) => d instanceof Blob)).toBe(true), { timeout: 3000 });
    expect(screen.getByText('Je réfléchis…')).toBeTruthy();
    act(() => ws().serverSays({ type: 'result', source: 'voice', heard: 'quelle heure est-il', reply: 'Il est 14 heures 02.' }));
    expect(screen.getByText('quelle heure est-il')).toBeTruthy();
    expect(screen.getByText('Vous (voix)')).toBeTruthy();
  });

  it('micro refusé : message clair', async () => {
    navigator.mediaDevices.getUserMedia = vi.fn(() => Promise.reject(new Error('denied')));
    await connect();
    fireEvent.click(screen.getByLabelText('Parler'));
    await waitFor(() => screen.getByRole('alert'));
    expect(screen.getByRole('alert').textContent).toContain('Micro refusé');
  });

  it('personne ne parle : rien envoyé', async () => {
    loud = false;
    await connect();
    fireEvent.click(screen.getByLabelText('Parler'));
    await waitFor(() => screen.getByText("J'écoute…"));
    fireEvent.click(screen.getByLabelText("Arrêter l'enregistrement"));
    await waitFor(() => screen.getByText(/Je n'ai rien entendu/));
    expect(ws().sent.length).toBe(0);
  });

  it('serveur coupé : statut et reconnexion', async () => {
    await connect();
    act(() => ws().close());
    expect(screen.getByText(/Serveur injoignable/, { selector: '.conn' })).toBeTruthy();
    await waitFor(() => expect(FakeWS.instances.length).toBeGreaterThan(1), { timeout: 3000 });
  });
});