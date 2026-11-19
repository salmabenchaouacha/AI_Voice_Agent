"""Google Agenda : lire les événements d'un jour, en ajouter un.

Mise en place, une seule fois (voir le README, section Google Agenda) :
  1. un projet Google Cloud avec l'API Google Calendar activée ;
  2. un identifiant OAuth « Application de bureau », téléchargé dans backend/google_credentials.json ;
  3. python mcp_servers/calendar_server.py --login  -> le navigateur demande l'autorisation, le jeton est gardé
     dans le dossier personnel (~/.assistant_google_token.json) ;
  4. dans mcp.json, passer "enabled" du serveur « agenda » à true.

Les fonctions acceptent un `svc` (service Google) en paramètre : les tests passent un faux, sans réseau.
"""
import os
import re
from datetime import date, datetime, time, timedelta

import config

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NOT_READY = ("L'agenda Google n'est pas encore connecté. Dans le dossier backend, lance : "
             "python mcp_servers/calendar_server.py --login")


class NotConnected(Exception):
    pass


# ---------- connexion ----------
def login() -> str:
    """Ouvre le navigateur pour autoriser l'accès à l'agenda, puis garde le jeton."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not os.path.exists(config.GOOGLE_CREDENTIALS):
        raise NotConnected(f"Fichier introuvable : {config.GOOGLE_CREDENTIALS}. Télécharge l'identifiant OAuth "
                           "« Application de bureau » depuis Google Cloud et enregistre-le sous ce nom.")
    creds = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS, SCOPES).run_local_server(port=0)
    with open(config.GOOGLE_TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return config.GOOGLE_TOKEN


def service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise NotConnected("Les bibliothèques Google manquent. Lance : "
                           "pip install google-api-python-client google-auth-oauthlib") from e
    if not os.path.exists(config.GOOGLE_TOKEN):
        raise NotConnected(NOT_READY)
    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(config.GOOGLE_TOKEN, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise NotConnected(NOT_READY)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ---------- dates dites à l'oral ----------
def parse_day(day: str, today: date | None = None) -> date | None:
    """« aujourd'hui », « demain », « après-demain », « vendredi », « 2026-11-21 », « 21/11 »."""
    today = today or date.today()
    d = (day or "").strip().lower()
    if d in ("", "aujourd'hui", "aujourd’hui", "today", "ce jour"):
        return today
    if d in ("demain", "tomorrow"):
        return today + timedelta(days=1)
    if d in ("après-demain", "apres-demain"):
        return today + timedelta(days=2)
    for i, nom in enumerate(JOURS):
        if d.removeprefix("ce ").removesuffix(" prochain") == nom:
            return today + timedelta(days=(i - today.weekday()) % 7 or 7)
    try:
        return date.fromisoformat(d)
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", d)
    if m:
        try:
            when = date(today.year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
        return when if when >= today else date(today.year + 1, when.month, when.day)
    return None


def day_label(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        return "Aujourd'hui"
    if d == today + timedelta(days=1):
        return "Demain"
    return f"{JOURS[d.weekday()].capitalize()} {d.day}/{d.month:02d}"


def _spoken_hour(hm: str) -> str:
    h, m = hm.split(":")
    return f"{int(h)} h {m}" if m != "00" else f"{int(h)} h"


# ---------- lecture ----------
def list_events(day: str = "aujourd'hui", svc=None, today: date | None = None) -> tuple[str, dict | None]:
    today = today or date.today()
    d = parse_day(day, today)
    if d is None:
        return f"Je n'ai pas compris le jour « {day} ».", None
    try:
        svc = svc or service()
    except NotConnected as e:
        return str(e), None
    start = datetime.combine(d, time.min).astimezone()
    end = start + timedelta(days=1)
    items = svc.events().list(calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
                              singleEvents=True, orderBy="startTime", maxResults=20).execute().get("items", [])
    events = []
    for it in items:
        s, e = it.get("start", {}), it.get("end", {})
        all_day = "dateTime" not in s
        events.append({"title": it.get("summary") or "(sans titre)", "allDay": all_day,
                       "time": "" if all_day else datetime.fromisoformat(s["dateTime"]).astimezone().strftime("%H:%M"),
                       "end": "" if all_day else datetime.fromisoformat(e["dateTime"]).astimezone().strftime("%H:%M")})
    label = day_label(d, today)
    card = {"kind": "agenda", "title": label, "date": d.isoformat(), "events": events}
    if not events:
        return f"{label}, rien dans ton agenda.", card
    parts = [f"{'toute la journée' if ev['allDay'] else 'à ' + _spoken_hour(ev['time'])}, {ev['title']}" for ev in events]
    n = len(events)
    return f"{label}, {n} événement{'s' if n > 1 else ''} : " + " ; ".join(parts) + ".", card


# ---------- ajout ----------
def create_event(title: str, start: str, duration_minutes: int = 60, svc=None,
                 now: datetime | None = None) -> tuple[str, dict | None]:
    """`start` : « AAAA-MM-JJ HH:MM » (heure locale)."""
    title = (title or "").strip()
    if not title:
        return "Quel est le titre de l'événement ?", None
    try:
        begin = datetime.strptime(re.sub(r"t", " ", (start or "").strip().lower(), count=1)[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return f"Je n'ai pas compris la date « {start} ». Donne-la sous la forme 2026-11-21 10:00.", None
    duration = max(5, min(int(duration_minutes or 60), 24 * 60))
    begin = begin.astimezone()
    if begin < (now or datetime.now()).astimezone() - timedelta(minutes=5):
        return "Cette date est déjà passée.", None
    finish = begin + timedelta(minutes=duration)
    try:
        svc = svc or service()
    except NotConnected as e:
        return str(e), None
    svc.events().insert(calendarId="primary", body={
        "summary": title,
        "start": {"dateTime": begin.isoformat()},
        "end": {"dateTime": finish.isoformat()},
    }).execute()
    label = day_label(begin.date())
    card = {"kind": "agenda", "title": label, "date": begin.date().isoformat(), "added": True,
            "events": [{"title": title, "allDay": False, "time": begin.strftime("%H:%M"), "end": finish.strftime("%H:%M")}]}
    return f"C'est ajouté à ton agenda : {title}, {label.lower()} à {_spoken_hour(begin.strftime('%H:%M'))}.", card
