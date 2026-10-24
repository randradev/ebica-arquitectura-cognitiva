"""
Arranca el servidor: `.venv/Scripts/python.exe -m ebica.api` desde la raíz del repo.

Carga `.env` y escucha solo en 127.0.0.1: las conversaciones no salen del PC (§13.3).
"""

import os

import uvicorn
from dotenv import load_dotenv

# CONSTANTE: puerto del backend; la consola de Vite le reenvía /api y /ws.
DEFAULT_PORT = 8000


def main() -> None:
    """Carga la configuración local y lanza uvicorn con la fábrica de la aplicación."""
    load_dotenv()
    uvicorn.run(
        "ebica.api.server:create_app",
        factory=True,
        host="127.0.0.1",
        port=int(os.environ.get("EBICA_API_PORT", DEFAULT_PORT)),
    )


if __name__ == "__main__":
    main()
