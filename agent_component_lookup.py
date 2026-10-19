import os
from dotenv import load_dotenv
from fasta2a.pydantic_ai import agent_to_a2a
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
import uvicorn
import logging

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

model = OpenAIChatModel(
    "default-model",  # Modell-Alias aus litellm_config.yaml, das echte Modell steht in .env (LLM_MODEL)
    provider=OpenAIProvider(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
)
logger = logging.getLogger(__name__)

# Bauteile im Schaltschrank (Demo-Daten): BMK -> (Bauteil, Artikelnummer)
COMPONENTS = {
    "=A1+S1-Q1": ("Motorschutzschalter 0,7-1A", "3RV2011-1JA10"),
    "=A1+S2-K3": ("Schütz 15kW 24V DC", "3RT2026-1BB40"),
    "=A1+S2-K4": ("Schütz 15kW 24V DC", "3RT2026-1BB40"),
    "=A1+S2-T1": ("Netzteil 24V DC 10A", "2904601"),
    "=A1+S2-A1": ("SPS CPU 1214C", "6ES7214-1AG40-0XB0"),
    "=A2+S1-Q12": ("Motorschutzschalter 11-16A", "3RV2021-4AA10"),
    "=A2+S1-U1": ("Frequenzumrichter V20 0,75kW", "6SL3210-5BB17-5UV1"),
}


def get_components(bmks: list[str]) -> str:
    """Liefert Bauteil und Artikelnummer zu jedem BMK (z. B. =A1+S2-K3)."""
    lines = []
    for bmk in bmks:
        bmk = bmk.strip().upper()
        if bmk not in COMPONENTS:
            logger.info(f"BMK {bmk} nicht gefunden")
            lines.append(f"{bmk} | nicht gefunden | -")
            continue
        component, article = COMPONENTS[bmk]
        logger.info(f"BMK {bmk}: {component}, {article}")
        lines.append(f"{bmk} | {component} | {article}")
    return "\n".join(lines)


# Die Tool-Funktion ist direkt die Ausgabe des Agenten (output_type): nur ein LLM-Aufruf pro Anfrage
agent = Agent(
    model,
    output_type=get_components,
    system_prompt="Rufe das Tool mit allen BMKs (z. B. =A1+S2-K3) aus der Anfrage auf.",
)


# Pydantic-AI-Agent in eine A2A-kompatible ASGI-App umwandeln
app = agent_to_a2a(agent)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8022)
