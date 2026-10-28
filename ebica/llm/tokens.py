"""
Estimación de tokens sin tokenizador (D1-10).

El presupuesto de la WorkingMemory (§5.6) y el tope del prompt necesitan saber
cuánto ocupa un texto. Se cuenta por palabras, con un factor calibrado contra el
`usage.prompt_tokens` que devuelve Ollama: en las conversaciones de CP8, el
total real del prompt dividido por el estimado dio 0,95–1,03 (mediana 0,99, n = 20).
Vive aparte para que la pizarra y el Prompt Assembler lo usen sin depender uno del otro.
"""

# CONSTANTE: tokens por palabra (D1-10), calibrada con Ollama en CP3, CP6 y CP9.
TOKENS_PER_WORD = 1.6


def estimate_tokens(text: str) -> int:
    """Estimación de tokens por palabras (D1-10)."""
    return round(len(text.split()) * TOKENS_PER_WORD)
