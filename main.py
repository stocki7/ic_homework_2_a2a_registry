import asyncio
import os
from uuid import uuid4
import httpx
import requests
from dotenv import load_dotenv

load_dotenv()  # Umgebungsvariablen aus .env laden

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
API_KEY = os.getenv("OPENAI_API_KEY")

# Agenten sind in litellm_config.yaml (Block "agents") registriert und laufen als eigene Container:
# docker compose up -d --build

HEADERS = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}

def discover_agents():
    """Holt alle registrierten Agenten von LiteLLM."""
    response = requests.get(f"{LITELLM_URL}/v1/agents", headers=HEADERS)
    response.raise_for_status()

    # Die Antwort ist eine Liste von Agenten-Objekten
    agents_data = response.json()

    # Zuordnung {Name: Agenten-ID} erstellen
    # Beispiel: {'agent-spare-parts': '8ff67c22-...'}
    return {a['agent_name']: a['agent_id'] for a in agents_data}

async def call_via_litellm(agent_id: str, prompt: str):
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        send_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "agent_id": agent_id,
                "message": {
                    "messageId": str(uuid4()),
                    "kind": "message",
                    "role": "user",
                    "parts": [{"kind": "text", "text": prompt}]
                }
            },
            "id": str(uuid4())
        }

        resp = await client.post(
            f"{LITELLM_URL}/v1/a2a/{agent_id}/message/send",
            json=send_payload,
            headers=headers
        )
        resp.raise_for_status()

        data = resp.json()

        # A2A- / JSON-RPC-Strukturen flexibel auswerten
        parts = data.get("result", {}).get("message", {}).get("parts", [])
        if not parts:
            parts = data.get("result", {}).get("parts", [])

        for entry in reversed(parts):
            # Text an den verschiedenen möglichen Stellen suchen
            if isinstance(entry, dict):
                if entry.get("kind") == "text" and "text" in entry:
                    return entry["text"].strip()
                if "content" in entry:
                    return str(entry["content"]).strip()
                if "text" in entry:
                    return str(entry["text"]).strip()

        # Fallback: unbekannte Struktur als Text zurückgeben
        if "result" in data:
            return str(data["result"]).strip()

        return "Keine Antwort des Agenten gefunden."

async def run():
    agents = discover_agents()
    print(f"Gefundene Agenten: {list(agents.keys())}")

    fault_report = ("In Schrank =A1+S2 ist das Schütz -K3 abgefallen und lässt sich nicht mehr einschalten. "
                    "Außerdem flackert die LED am Netzteil -T1. "
                    "Auftragsnummer 9004711 bitte ignorieren, die ist alt.")

    # Schritt 1: BMKs extrahieren
    print("Rufe BMK-Extraktions-Agent auf...")
    # Exakter Name aus der Registry
    extractor_id = agents.get("agent-bmk-extraction")
    if not extractor_id:
        print("Fehler: 'agent-bmk-extraction' nicht in der Registry gefunden.")
        return

    found_bmks = await call_via_litellm(extractor_id, fault_report)
    print(f"Gefundene BMKs: {found_bmks}")

    # Schritt 2: Bauteile nachschlagen
    print("Rufe Bauteil-Agent auf...")
    component_id = agents.get("agent-component-lookup")
    if not component_id:
        print("Fehler: 'agent-component-lookup' nicht in der Registry gefunden.")
        return

    components = await call_via_litellm(component_id, f"Bauteile zu: {found_bmks}")
    print(f"Gefundene Bauteile:\n{components}")

    # Schritt 3: Ersatzteile prüfen
    print("Rufe Ersatzteil-Agent auf...")
    spare_parts_id = agents.get("agent-spare-parts")
    if not spare_parts_id:
        print("Fehler: 'agent-spare-parts' nicht in der Registry gefunden.")
        return

    final_info = await call_via_litellm(spare_parts_id, f"Lagerbestand und Lieferzeit für die Artikel in:\n{components}")

    print("\n--- ERGEBNIS ---")
    print(f"{components}\n\n{final_info}")

if __name__ == "__main__":
    asyncio.run(run())
