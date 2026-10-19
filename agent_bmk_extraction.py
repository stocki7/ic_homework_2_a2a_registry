import os
import re
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
        api_key=os.getenv("OPENAI_API_KEY")
    )
)
logger = logging.getLogger(__name__)


# Betriebsmittelkennzeichen (BMK) nach IEC 81346: optional Anlage (=A1), optional Ort (+S2), Betriebsmittel (-K3)
BMK_PATTERN = re.compile(
    r"(?<![\w=+\-])(=[A-Z]\w*)?(\+[A-Z]\w*)?(-[A-Z]{1,3}\d{1,4})?(?!\w)",
    re.IGNORECASE
)


def extract_bmk(text: str) -> str:
    """
    Nimmt den unveränderten Text der Störungsmeldung und extrahiert alle Betriebsmittelkennzeichen (BMK, z. B. =A1+S2-K3).
    Betriebsmittel ohne Präfix (z. B. -K3) werden mit der zuletzt genannten Anlage/dem Ort ergänzt (z. B. =A1+S2).
    Reine Zahlen (z. B. Auftragsnummern) werden ignoriert.
    Args:
        text: Die komplette Eingabe des Benutzers.
    """
    logger.info(f"Extrahiere BMKs aus dem Text: {text}")
    bmks = []
    plant, location = "", ""
    for match in BMK_PATTERN.finditer(text):
        new_plant, new_location, device = match.groups()
        if new_plant:
            plant, location = new_plant.upper(), ""
        if new_location:
            location = new_location.upper()
        if device and f"{plant}{location}{device.upper()}" not in bmks:
            bmks.append(f"{plant}{location}{device.upper()}")

    logger.info(f"Gefilterte BMKs: {bmks}")
    return ", ".join(bmks) if bmks else "Keine BMKs gefunden"


# Die Tool-Funktion ist direkt die Ausgabe des Agenten (output_type): das LLM ruft sie genau einmal auf
# und ihr Rückgabewert ist die Antwort. Spart gegenüber @agent.tool_plain einen LLM-Aufruf (Gemini-Free-Tier-Limit).
agent = Agent(
    model,
    output_type=extract_bmk,
    system_prompt=(
        "Du bist eine strikte Extraktions-Engine. "
        "Deine EINZIGE Aufgabe ist es, das Tool mit dem unveränderten, vollständigen Eingabetext aufzurufen."
    )
)


# Als A2A-Agent bereitstellen
app = agent_to_a2a(agent)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8021, log_level="info")
