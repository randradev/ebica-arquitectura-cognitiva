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
