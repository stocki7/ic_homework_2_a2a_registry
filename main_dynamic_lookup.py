import asyncio
import json
import os
import httpx
from dotenv import load_dotenv
from main import call_via_litellm

load_dotenv()

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
API_KEY = os.getenv("OPENAI_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "x-litellm-api-key": API_KEY,
    "accept": "application/json",
}

async def fetch_available_agents(client: httpx.AsyncClient) -> list[dict]:
    """Holt alle registrierten Agenten inklusive ihrer Beschreibung aus der Registry."""
    resp = await client.get(f"{LITELLM_URL}/v1/agents", headers=headers)
    resp.raise_for_status()
    return resp.json()

async def route_query_to_agents(client: httpx.AsyncClient, query: str, agents: list[dict]) -> list[str]:
    """Ein LLM-Router plant anhand der Agentenbeschreibungen, welche Agenten in welcher Reihenfolge nötig sind."""

    # 1. Agenten-Metadaten als übersichtliche Liste für den Router aufbereiten
    agent_manifest = [
        {
            "agent_id": a.get("agent_id"),
            "name": a.get("agent_name"),
            "description": a.get("agent_card_params", {}).get("description", "Keine Beschreibung"),
        }
        for a in agents
    ]

    system_prompt = (
        "Du bist ein Router. Analysiere die Anfrage und plane, welche der verfügbaren Agenten "
        "in welcher Reihenfolge nötig sind, um sie vollständig zu beantworten. "
        "Die Agenten arbeiten als Kette: der erste Agent bekommt die Anfrage, jeder weitere nur das Ergebnis des vorherigen Agenten. "
        "Wähle nur Agenten, die wirklich gebraucht werden. "
        f"Verfügbare Agenten:\n{agent_manifest}"
    )

    # 2. Router (über den LiteLLM-Proxy) die geordnete Liste der Agenten-IDs bestimmen lassen
    # Dafür wird Structured Output (json_schema) verwendet
    response = await client.post(
        f"{LITELLM_URL}/v1/chat/completions",
        headers=headers,
        json={
            "model": "default-model",  # Modell-Alias aus litellm_config.yaml, echtes Modell in .env (LLM_MODEL)
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Plane die Agenten für die Anfrage: {query}"}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_plan",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "agent_ids": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["agent_ids"]
                    }
                }
            }
        }
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)["agent_ids"]

timeout_config = httpx.Timeout(
    connect=10.0,  # 10 s Verbindungs-Timeout
    read=60.0,     # 60 s Lese-Timeout für die LLM-Verarbeitung
    write=10.0,    # 10 s Schreib-Timeout
    pool=10.0      # 10 s Wartezeit auf eine freie Verbindung
)

async def main():
    async with httpx.AsyncClient(timeout=timeout_config) as client:
        try:
            #prompt = "Wie viele Stück von Artikel 3RT2026-1BB40 sind lagernd und wie lange ist die Lieferzeit von 2904601?"
            prompt = ("In Schrank =A1+S2 ist das Schütz -K3 abgefallen und lässt sich nicht mehr einschalten. "
                                "Außerdem flackert die LED am Netzteil -T1. "
                                "Auftragsnummer 9004711 bitte ignorieren, die ist alt.")
            print(f"Anfrage: {prompt}")

            # Verfügbare Agenten aus der Registry holen
            agents = await fetch_available_agents(client)
            agent_names = {a["agent_id"]: a["agent_name"] for a in agents}
            print(f"Gefundene Agenten: {list(agent_names.values())}")

            # Router plant anhand der Beschreibungen, welche Agenten in welcher Reihenfolge nötig sind
            plan = [agent_id for agent_id in await route_query_to_agents(client, prompt, agents) if agent_id in agent_names]
            print(f"Plan des Routers: {' -> '.join(agent_names[agent_id] for agent_id in plan)}")

            # Agenten nacheinander aufrufen: der erste bekommt die Anfrage, jeder weitere das Ergebnis des vorherigen
            message = prompt
            results = []
            for step, agent_id in enumerate(plan, start=1):
                print(f"Schritt {step}: Rufe {agent_names[agent_id]} auf...")
                message = await call_via_litellm(agent_id, message)
                print(f"Ergebnis:\n{message}")
                results.append(message)

            print("\n--- ERGEBNIS ---")
            print("\n\n".join(results))

        except Exception as e:
            print(f"Ablauf fehlgeschlagen: {e}")

if __name__ == "__main__":
    asyncio.run(main())
