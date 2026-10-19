# Homework 2 - Option A: Verteiltes Remote-A2A-System mit dynamischem Registry-Lookup

**Industrial Computing, MCI - Hausübung Teil 2, Technical Track**

**Stockinger Rene**

Erweitert **Sample 6 (a2a remote)** aus dem Vorlesungs-Repo
[chmaurer/mci_industrial_computing](https://github.com/chmaurer/mci_industrial_computing)
von zwei auf drei Agenten. Jeder Agent läuft in einem eigenen Docker-Container auf einem
eigenen Port. Die Agenten werden zur Laufzeit über die Agenten-Registry von LiteLLM gefunden
und über das A2A-Gateway von LiteLLM aufgerufen.

## Was umgesetzt wurde

Domäne: Störungsmeldung an einem Schaltschrank. Die drei Agenten bearbeiten die Meldung gemeinsam,
das Ergebnis eines Agenten ist jeweils die Eingabe des nächsten:

| Agent | Port | Aufgabe |
|---|---|---|
| `agent-bmk-extraction` | 8021 | Extrahiert Betriebsmittelkennzeichen (BMK, z.B. `=A1+S2-K3`) aus dem Freitext, ignoriert Auftragsnummern |
| `agent-component-lookup` | 8022 | Liefert Bauteil und Artikelnummer zu jedem BMK |
| `agent-spare-parts` | 8023 | Liefert Lagerbestand, Lagerort und Lieferzeit zu jeder Artikelnummer |

**Dynamischer Registry-Lookup:** Die Agenten sind in `litellm_config.yaml` (Block `agents`) mit Name,
Beschreibung und URL registriert. Die Clients kennen weder URLs noch IDs:

* `main.py` holt sich über `GET /v1/agents` die IDs zu den Agentennamen und ruft die drei Agenten
  nacheinander über `POST /v1/a2a/{agent_id}/message/send` auf (wie in Sample 6).
* `main_dynamic_lookup.py` lässt ein LLM anhand der Agentenbeschreibungen aus der Registry planen,
  welche Agenten in welcher Reihenfolge eine Anfrage bearbeiten (erweiterter Router aus Sample 6).
  Die geplanten Agenten werden dann automatisch als Kette aufgerufen: Bei einer Störungsmeldung sind
  das alle drei, bei einer reinen Lagerfrage z.B. nur `agent-spare-parts`.

## Dateien

```
agent_bmk_extraction.py      Agent 1 (Port 8021)
agent_component_lookup.py    Agent 2 (Port 8022)
agent_spare_parts.py         Agent 3 (Port 8023)
Dockerfile.*                 ein Dockerfile pro Agent
litellm_config.yaml          LiteLLM: Modell-Alias + Agenten-Registry
docker-compose.yml           startet LiteLLM (+ Postgres für die Oberfläche) und die drei Agenten
main.py                      Client: Registry-Lookup + Kette aus drei Agenten
main_dynamic_lookup.py       Client: LLM-Router plant die Agenten-Kette und ruft sie auf
.env.example                 Vorlage für die Umgebungsvariablen
```

## Einrichtung

Voraussetzungen: Docker Desktop, [uv](https://docs.astral.sh/uv/) und ein Gemini-API-Key.

```bash
uv sync
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
# .env bearbeiten: GEMINI_API_KEY eintragen, optional LLM_MODEL (Gemini-Modell) ändern
```

## Ausführen

**1. LiteLLM und die drei Agenten starten** (jeweils eigener Container und Port):

```bash
docker compose up -d --build
docker compose ps
```

LiteLLM braucht beim ersten Start etwa 30-60 Sekunden (Einrichtung der Datenbank), bis es erreichbar ist.

**2. Registrierte Agenten prüfen** (optional):

```bash
curl -H "Authorization: Bearer <OPENAI_API_KEY aus .env>" http://localhost:4000/v1/agents
# Windows PowerShell: curl.exe statt curl verwenden
```

Alternativ in der LiteLLM-Oberfläche: <http://localhost:4000/ui>, Benutzername `admin`,
Passwort = `OPENAI_API_KEY` aus `.env`, dann Menüpunkt *Agents*.

**3. Clients ausführen:**

```bash
uv run python main.py
uv run python main_dynamic_lookup.py
```

**Logs der Agenten** (Tool-Aufrufe):

```bash
docker compose logs -f agent-bmk-extraction agent-component-lookup agent-spare-parts
```

**Stoppen:** `docker compose down`

## Beispielausgabe `main_dynamic_lookup.py`

```
Anfrage: In Schrank =A1+S2 ist das Schütz -K3 abgefallen und lässt sich nicht mehr einschalten. Außerdem flackert die LED am Netzteil -T1. Auftragsnummer 9004711 bitte ignorieren, die ist alt.
Gefundene Agenten: ['agent-bmk-extraction', 'agent-component-lookup', 'agent-spare-parts']
Plan des Routers: agent-bmk-extraction -> agent-component-lookup -> agent-spare-parts
Schritt 1: Rufe agent-bmk-extraction auf...
Ergebnis:
=A1+S2-K3, =A1+S2-T1
Schritt 2: Rufe agent-component-lookup auf...
Ergebnis:
=A1+S2-K3 | Schütz 15kW 24V DC | 3RT2026-1BB40
=A1+S2-T1 | Netzteil 24V DC 10A | 2904601
Schritt 3: Rufe agent-spare-parts auf...
Ergebnis:
Artikel 3RT2026-1BB40: 2 Stk. lagernd in Regal B4.
Artikel 2904601: nicht lagernd (Regal C1), Lieferzeit: 5 Arbeitstage.

--- ERGEBNIS ---
=A1+S2-K3, =A1+S2-T1

=A1+S2-K3 | Schütz 15kW 24V DC | 3RT2026-1BB40
=A1+S2-T1 | Netzteil 24V DC 10A | 2904601

Artikel 3RT2026-1BB40: 2 Stk. lagernd in Regal B4.
Artikel 2904601: nicht lagernd (Regal C1), Lieferzeit: 5 Arbeitstage.
```

Die Antworten der Agenten kommen direkt aus ihren Tool-Funktionen und haben daher immer dieses Format.

## Hinweise

* Die Tool-Funktion jedes Agenten ist als `output_type` hinterlegt (statt `@agent.tool_plain` wie in Sample 6):
  Das LLM ruft sie genau einmal auf und ihr Rückgabewert ist direkt die Antwort des Agenten. Das spart pro Agent
  einen LLM-Aufruf (wichtig für das Gemini-Free-Tier-Limit) und liefert immer das gleiche Ausgabeformat.
* Das Gemini-Modell wird nur in `.env` (`LLM_MODEL`) festgelegt. Agenten und Router verwenden den festen
  LiteLLM-Alias `default-model`. Nach einer Änderung des Modells: `docker compose up -d` (startet LiteLLM neu).

## Mögliche Erweiterung: Root-Agent

`main_dynamic_lookup.py` plant die Agenten-Kette **einmal am Anfang** (statische Planung) und arbeitet sie dann
der Reihe nach ab. Die Koordination liegt dabei im Client-Skript.

Eine Erweiterung wäre ein eigener **Root-Agent** (vgl. Vorlesungsfolie 97: „Establish a root agent, which
coordinates multiple sub-agents“), der selbst als A2A-Agent in einem eigenen Container läuft, in der Registry
eingetragen ist und die Sub-Agenten als Werkzeuge nutzt:

* **Dynamische statt statischer Planung:** Der Root-Agent entscheidet nach jedem Schritt neu, welcher Agent als
  Nächstes gebraucht wird, und kann auf Zwischenergebnisse reagieren (z.B. ein unbekanntes BMK überspringen
  oder bei einem ausgefallenen Agenten ein Teilergebnis liefern).
* **Gezielte Weitergabe:** Jeder Sub-Agent bekommt nur die Daten, die er braucht (z.B. nur die Artikelnummern),
  statt immer das komplette Ergebnis des vorherigen Agenten.
* **Wiederverwendbar:** Jeder Client könnte die Koordination per A2A beauftragen, nicht nur dieses Skript.

Bewusst nicht umgesetzt, weil ein Root-Agent deutlich mehr LLM-Aufrufe braucht (mehrere eigene Planungs-Schritte
plus die Sub-Agenten) und ich beim Gemini-Free-Tier-Limit so schon schnell ans Limit gekommen bin.
