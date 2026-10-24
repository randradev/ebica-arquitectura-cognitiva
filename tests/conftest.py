"""
Configuración común de pytest.

Carga `.env` (si existe) antes de las pruebas, para que las de integración
encuentren las credenciales de Neo4j y la URL del LLM sin pasos manuales.
No sobrescribe variables ya definidas en la terminal.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
