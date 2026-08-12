# RedAlert

Eigener Reddit-Keyword-Listener als F5Bot-Ersatz: durchsucht periodisch Reddit nach
konfigurierbaren Keyword-Mustern (beliebig viele Keywords, Teilstring-Matching,
Ausschlussbegriffe, mehrere Formulierungen pro Thema) und schickt bei neuen Treffern
eine Nachricht per Telegram-Bot.

Laeuft komplett auf GitHub Actions, kein eigener Server, keine laufenden Kosten.

## Hinweis zum Reddit-Zugriff

Dieses Projekt nutzt **Reddits oeffentliche, unauthentifizierte Atom/RSS-Feeds**
(z. B. `reddit.com/r/<sub>/new.rss`) statt der offiziellen OAuth-API. Grund: Reddit
hat die Selbstregistrierung neuer API-Apps geschlossen (Responsible Builder Policy,
Stand 2026) und verlangt seither eine vorherige Genehmigung per Support-Ticket; der
Antrag fuer dieses persoenliche Projekt wurde abgelehnt.

Beim Bau wurde live getestet, dass die frueher ueblichen `.json`-Endpunkte
(`new.json` etc.) fuer unauthentifizierte Anfragen inzwischen **hart geblockt sind**
(HTTP 403, auch mit plausiblem Browser-User-Agent). Die `.rss`-Endpunkte
funktionieren dagegen weiterhin mit einem ehrlichen, nicht-generischen User-Agent —
`monitor.py` nutzt deshalb diese. Das heisst konkret:

- Auch die `.rss`-Endpunkte sind inoffiziell und nicht supported — sie koennen sich
  jederzeit ohne Vorwarnung aendern, weiter eingeschraenkt oder abgeschaltet werden.
- Sie unterliegen einem strengeren, undokumentierten Rate-Limiting als die offizielle
  API (beim Testen wurde nach mehreren schnellen Anfragen kurzzeitig ein HTTP 429
  beobachtet). Der Workflow macht pro Lauf nur zwei Requests, das sollte unkritisch
  sein.
- `monitor.py` ist entsprechend defensiv gebaut: ein fehlgeschlagener oder nicht
  parsebarer Request bricht den Lauf nicht ab, sondern wird uebersprungen und
  geloggt.

**Bevor du das dauerhaft laufen laesst**, pruefe selbst kurz Reddits aktuelle
Nutzungsbedingungen und die [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
dazu, ob und wie automatisierter Zugriff auf diese oeffentlichen Endpunkte erlaubt
ist. Diese Anleitung ersetzt keine eigene Pruefung der ToS. Falls du spaeter doch noch
offiziellen API-Zugriff bekommst (z. B. nach einem erneuten Antrag), lohnt es sich,
wieder auf die offizielle OAuth-API mit PRAW umzustellen — zuverlaessiger und
ToS-konform per Definition.

## Setup

### 1. Telegram-Bot erstellen

1. In Telegram den offiziellen [@BotFather](https://t.me/BotFather) oeffnen und
   `/newbot` schicken.
2. Namen und Username vergeben (Username muss auf `bot` enden, z. B.
   `redalert_keyword_bot`).
3. BotFather antwortet mit dem **Bot-Token** (Format `123456789:AA...`) — kopieren.
4. Dem neuen Bot eine beliebige Nachricht schicken (z. B. `/start`), damit er weiss,
   dass er dir schreiben darf. Ohne diesen Schritt kann der Bot dir keine
   Nachrichten senden.
5. Deine **Chat-ID** herausfinden: im Browser
   `https://api.telegram.org/bot<DEIN_BOT_TOKEN>/getUpdates` aufrufen (Token
   einsetzen), nachdem du dem Bot geschrieben hast. In der JSON-Antwort steht unter
   `"message":{"chat":{"id": ...}}` deine Chat-ID (eine Zahl, ggf. negativ falls es
   eine Gruppe statt eines Privatchats ist).

### 2. GitHub Actions Secrets hinterlegen

Im Repo unter **Settings → Secrets and variables → Actions → New repository secret**
folgende drei Secrets anlegen:

| Secret | Wert |
| --- | --- |
| `REDDIT_USER_AGENT` | z. B. `redalert-keyword-monitor/1.0 by u/<dein-reddit-username>` |
| `TELEGRAM_BOT_TOKEN` | Bot-Token aus Schritt 1 |
| `TELEGRAM_CHAT_ID` | Chat-ID aus Schritt 1 |

`REDDIT_USER_AGENT` sollte aussagekraeftig und ehrlich sein, kein generischer String
wie der Standard-User-Agent von `requests` — Reddit blockt solche Anfragen deutlich
haeufiger, gerade bei unauthentifiziertem Zugriff.

### 3. Testlauf

Nach dem Push: im Reiter **Actions** den Workflow **"Reddit Keyword Monitor"** oeffnen
und ueber **"Run workflow"** (workflow_dispatch) manuell starten, statt auf den
naechsten Cron-Lauf zu warten. Im Log siehst du, wie viele neue Items geprueft und wie
viele Alerts gesendet wurden (bzw. ob Requests fehlgeschlagen sind).

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
  neuesten Posts (Titel + Body) und Kommentare der konfigurierten Subreddits ueber
  Reddits oeffentliche `.rss`-Feeds (Atom-Format).
- Bereits gemeldete IDs stehen in [seen_ids.json](seen_ids.json) (auf die letzten 5.000
  Eintraege begrenzt) und werden nach jedem Lauf automatisch zurueck ins Repo
  committet — das verhindert doppelte Alerts, ganz ohne externe Datenbank.
- Bei einem Treffer wird eine Telegram-Nachricht mit Keyword-Gruppe, Subreddit,
  Ausschnitt und direktem Link verschickt.

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
│   └── notifier.py                 # Telegram-Benachrichtigungen
├── tests/
│   └── test_matcher.py             # Unit-Tests fuer das Matching
├── requirements.txt
└── README.md
```

## Lokal entwickeln / testen

```bash
pip install -r requirements.txt
pip install pytest
pytest tests/
```

Fuer einen lokalen Testlauf des Monitors selbst muessen die drei Umgebungsvariablen
(`REDDIT_USER_AGENT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) gesetzt sein, z. B.
per `.env` + `export $(cat .env | xargs)` oder direkt im Terminal.
