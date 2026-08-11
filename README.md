# RedAlert

Eigener Reddit-Keyword-Listener als F5Bot-Ersatz: durchsucht periodisch Reddit nach
konfigurierbaren Keyword-Mustern (beliebig viele Keywords, Teilstring-Matching,
Ausschlussbegriffe, mehrere Formulierungen pro Thema) und schickt bei neuen Treffern
eine Nachricht an einen Discord-Webhook.

Laeuft komplett auf GitHub Actions, kein eigener Server, keine laufenden Kosten.

## Setup

### 1. Reddit-App registrieren

1. Gehe zu [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps).
2. "create app" (bzw. "create another app") klicken.
3. Typ **"script"** waehlen.
4. Name frei waehlbar, "redirect uri" kann z. B. `http://localhost:8080` sein.
5. Nach dem Erstellen findest du direkt unter dem App-Namen die `client_id`
   (kurze Zeichenfolge) und daneben das `secret`.

### 2. Discord-Webhook erstellen

1. In einem Discord-Server (auch ein privater Server nur fuer dich reicht) →
   Kanaleinstellungen des Zielkanals → **Integrationen** → **Webhook erstellen**.
2. Webhook-URL kopieren.

### 3. GitHub Actions Secrets hinterlegen

Im Repo unter **Settings → Secrets and variables → Actions → New repository secret**
folgende vier Secrets anlegen:

| Secret | Wert |
| --- | --- |
| `REDDIT_CLIENT_ID` | `client_id` aus Schritt 1 |
| `REDDIT_CLIENT_SECRET` | `secret` aus Schritt 1 |
| `REDDIT_USER_AGENT` | z. B. `redalert-keyword-monitor/1.0 by u/<dein-reddit-username>` |
| `DISCORD_WEBHOOK_URL` | Webhook-URL aus Schritt 2 |

`REDDIT_USER_AGENT` sollte aussagekraeftig und ehrlich sein, kein generischer String —
Reddit verlangt das fuer API-Zugriffe.

### 4. Testlauf

Nach dem Push: im Reiter **Actions** den Workflow **"Reddit Keyword Monitor"** oeffnen
und ueber **"Run workflow"** (workflow_dispatch) manuell starten, statt auf den
naechsten Cron-Lauf zu warten. Im Log siehst du, wie viele neue Items geprueft und wie
viele Alerts gesendet wurden.

## Keywords konfigurieren

Alle Suchbegriffe stehen in [keywords.yaml](keywords.yaml) und lassen sich ohne
Code-Aenderung erweitern. Jeder Eintrag ist eine Gruppe:

```yaml
- name: "Litmaps Alternative"
  match_any:
    - "litmaps alternative"
    - "alternative to litmaps"
  case_sensitive: false
```

- **match_any**: Treffer, wenn irgendeine Phrase als Teilstring vorkommt (nicht nur
  ganzes Wort).
- **exclude_any** (optional): unterdrueckt den Treffer, wenn zusaetzlich eine dieser
  Phrasen vorkommt.
- **case_sensitive** (optional, Standard `false`): Gross-/Kleinschreibung beachten.

## Subreddits konfigurieren

In [config.yaml](config.yaml) laesst sich einstellen, ob eine kuratierte
Subreddit-Liste oder ganz Reddit (`r/all`) durchsucht wird. Standard ist die kuratierte
Liste — bessere Trefferqualitaet, weniger Rate-Limit-Last:

```yaml
subreddits:
  - Zotero
  - AskAcademia
  - PhD
  - GradSchool
  - labrats
search_all: false
```

## Wie es funktioniert

- Alle 45 Minuten (Cron) bzw. manuell via `workflow_dispatch` prueft der Workflow die
  neuesten Posts (Titel + Body) und Kommentare der konfigurierten Subreddits.
- Bereits gemeldete IDs stehen in [seen_ids.json](seen_ids.json) (auf die letzten 5.000
  Eintraege begrenzt) und werden nach jedem Lauf automatisch zurueck ins Repo
  committet — das verhindert doppelte Alerts, ganz ohne externe Datenbank.
- Bei einem Treffer wird eine Discord-Nachricht (Embed) mit Keyword-Gruppe, Subreddit,
  Ausschnitt und direktem Link verschickt.

**Hinweis zur Implementierung:** Das Skript nutzt PRAWs `.new()` / `.comments()`
Listings statt der Streaming-Funktionen (`stream.submissions()` / `stream.comments()`).
Die Streaming-Funktionen sind fuer dauerhaft laufende Prozesse gedacht und blockieren
unbegrenzt — das passt nicht zu einem kurzlebigen GitHub-Actions-Job, der alle paar
Minuten neu startet. Ein begrenzter Durchgang pro Lauf plus Dedup ueber
`seen_ids.json` erreicht dasselbe Ergebnis zuverlaessiger in diesem Kontext.

## Projektstruktur

```
RedAlert/
├── .github/workflows/monitor.yml   # Cron + manueller Trigger
├── keywords.yaml                   # Keyword-Gruppen (frei erweiterbar)
├── config.yaml                     # Subreddit-Liste / r-all-Umschalter
├── seen_ids.json                   # wird automatisch aktualisiert
├── src/
│   ├── monitor.py                  # Hauptskript
│   ├── matcher.py                  # Keyword-Matching-Logik
│   └── notifier.py                 # Discord-Webhook-Versand
├── tests/
│   └── test_matcher.py             # Unit-Tests fuer das Matching
├── requirements.txt
└── README.md
```

## Wichtiger Hinweis zu Reddits Nutzungsbedingungen

Bevor du das Projekt dauerhaft laufen laesst: pruefe selbst kurz Reddits aktuelle
Developer-Terms ([reddit.com/wiki/api-terms](https://www.reddit.com/wiki/api-terms)
bzw. die dort verlinkten aktuellen Bedingungen), insbesondere zu erlaubter
Abfragefrequenz und zulaessigen Anwendungsfaellen fuer ein "script"-App-Konto. Diese
Anleitung ersetzt keine eigene Pruefung der ToS.

## Lokal entwickeln / testen

```bash
pip install -r requirements.txt
pip install pytest
pytest tests/
```

Fuer einen lokalen Testlauf des Monitors selbst muessen die vier Umgebungsvariablen
(`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`,
`DISCORD_WEBHOOK_URL`) gesetzt sein, z. B. per `.env` + `export $(cat .env | xargs)`
oder direkt im Terminal.
