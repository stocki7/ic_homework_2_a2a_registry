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

# Ersatzteillager (Demo-Daten): Artikelnummer -> (Bestand, Lagerort, Lieferzeit in Arbeitstagen)
STOCK = {
    "3RV2011-1JA10": (4, "Regal A2", 3),
    "3RT2026-1BB40": (2, "Regal B4", 7),
    "2904601": (0, "Regal C1", 5),
    "6ES7214-1AG40-0XB0": (0, "Schrank E1", 21),
    "3RV2021-4AA10": (1, "Regal A2", 5),
}


def get_stock(article_numbers: list[str]) -> str:
    """Liefert Lagerbestand, Lagerort und Lieferzeit zu jeder Artikelnummer."""
    lines = []
    for article_no in article_numbers:
        article_no = article_no.strip().upper()
        if article_no not in STOCK:
            logger.info(f"Artikel {article_no} nicht im Lager geführt")
            lines.append(f"Artikel {article_no}: nicht im Lager geführt, bitte beim Einkauf anfragen.")
            continue
        qty, location, lead_time = STOCK[article_no]
        logger.info(f"Artikel {article_no}: Bestand={qty}, Lagerort={location}, Lieferzeit={lead_time}")
        if qty == 0:
            lines.append(f"Artikel {article_no}: nicht lagernd ({location}), Lieferzeit: {lead_time} Arbeitstage.")
        else:
            lines.append(f"Artikel {article_no}: {qty} Stk. lagernd in {location}.")
    return "\n".join(lines)


# Die Tool-Funktion ist direkt die Ausgabe des Agenten (output_type): nur ein LLM-Aufruf pro Anfrage
agent = Agent(
    model,
    output_type=get_stock,
    system_prompt="Rufe das Tool mit allen Artikelnummern (z. B. 3RT2026-1BB40 oder 2904601) aus der Anfrage auf.",
)


# Pydantic-AI-Agent in eine A2A-kompatible ASGI-App umwandeln
app = agent_to_a2a(agent)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8023)
