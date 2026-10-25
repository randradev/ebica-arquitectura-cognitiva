# EBICA

Motor cognitivo para entidades virtuales con memoria biográfica, afecto dinámico,
personalidad y procesos autónomos. La referencia del proyecto es
[`docs/EBICA_documento_base.md`](docs/EBICA_documento_base.md); el avance por fases está en `docs/fase-N/`.

## Entorno de desarrollo (Windows)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

Copia `.env.example` como `.env` para la configuración local.

### Embeddings (opcional para las pruebas unitarias)

Los embeddings corren en CPU. Instala `torch` **antes** y desde el índice de CPU de
PyTorch; si no, `pip` puede traer la variante con CUDA, que pesa varios GB:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,embeddings]"
```

Las pruebas unitarias usan un embedder falso y no necesitan este paso.

## Neo4j (memoria)

Requiere Docker Desktop y un `.env` con `NEO4J_PASSWORD` (la contraseña se fija
la primera vez que se crea el volumen de datos).

```powershell
docker compose up -d      # levanta Neo4j (Browser en http://localhost:7474)
docker compose stop       # lo detiene; los datos se conservan en el volumen
```

Las pruebas y los scripts cargan `.env` automáticamente (`python-dotenv`).

## Servidor y consola

Con Ollama y Neo4j encendidos, en dos terminales:

```powershell
.venv\Scripts\python.exe -m ebica.api     # backend en http://127.0.0.1:8000
cd console; npm install; npm run dev      # consola en http://127.0.0.1:5173
```

La consola permite crear o cargar una entidad, chatear con ella y ver en vivo
todos los eventos del motor (incluido el prompt exacto de cada `llm.request`).
