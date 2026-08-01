"""Rotating topic bank for app.workers.headline_scheduler.

Each entry pairs a concrete keto-recipe-community topic with an angle
instruction in the same "100% commit to this angle" style as
apps/web/lib/content-angles.ts (that file is frontend-only, read by a
human picking an angle in the /generate wizard; this is the backend
equivalent for content nobody picks by hand). Deliberately skips the
VENTA/sales angle — the whole point of this feed is community value, not
pitching the recipe book on every post; a human can still do that
manually via /generate.

HeadlineSchedule.topic_rotation_index cycles through this list one entry
at a time so consecutive auto-posts never repeat the same topic or angle.
"""

from __future__ import annotations

HEADLINE_TOPICS: list[dict[str, str]] = [
    {
        "topic": "Por qué el aguacate es uno de los alimentos más versátiles en keto",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable — no una receta completa ni una venta.",
    },
    {
        "topic": "El error más común al empezar keto: no reponer electrolitos",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable — explica el porqué y cómo evitarlo.",
    },
    {
        "topic": "¿Por qué algunas grasas saludables ayudan a sentir saciedad por más tiempo?",
        "objective": "Este post debe ser 100% una curiosidad o dato interesante — el título plantea la pregunta sin revelar toda la respuesta.",
    },
    {
        "topic": "Sustituir el arroz por coliflor en platos keto: cómo lograr la mejor textura",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable sobre esa sustitución puntual.",
    },
    {
        "topic": "Cómo saber si estás en cetosis sin usar tiras reactivas",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable — señales reales del cuerpo.",
    },
    {
        "topic": "El mito de que toda grasa es mala: qué dice la evidencia sobre las grasas en keto",
        "objective": "Este post debe ser 100% una curiosidad o dato interesante que desmonte un mito común.",
    },
    {
        "topic": "Por qué el queso es un aliado en keto y cuáles son las mejores opciones",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, no una receta completa.",
    },
    {
        "topic": "Lo que realmente significa 'macros' en una dieta keto y cómo calcularlos simple",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, explicado de forma simple.",
    },
    {
        "topic": "Por qué cortar cebolla te hace llorar y el truco real para evitarlo",
        "objective": "Este post debe ser 100% una curiosidad o dato interesante — desarrolla el porqué científico.",
    },
    {
        "topic": "Snacks keto de emergencia para cuando el hambre llega fuera de casa",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, con opciones concretas.",
    },
    {
        "topic": "Cómo mantener la constancia con keto sin sentir que te estás privando de todo",
        "objective": "Este post debe ser 100% una reflexión personal y cercana sobre el proceso de cambio de hábitos.",
    },
    {
        "topic": "Lo que aprendí de las recaídas al hacer un cambio de alimentación",
        "objective": "Este post debe ser 100% una reflexión personal y cercana, priorizando el tono emocional y honesto.",
    },
    {
        "topic": "Por qué el efecto rebote pasa tanto y cómo un cambio sostenible lo evita",
        "objective": "Este post debe ser 100% una reflexión personal y cercana sobre hábitos sostenibles, no una promesa de resultados.",
    },
    {
        "topic": "Los mejores endulzantes aptos para keto y en qué se diferencian",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, comparando opciones reales.",
    },
    {
        "topic": "Cómo leer una etiqueta nutricional para saber si un producto es realmente keto",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, con pasos concretos.",
    },
    {
        "topic": "Por qué beber suficiente agua importa todavía más en una dieta baja en carbohidratos",
        "objective": "Este post debe ser 100% una curiosidad o dato interesante sobre el porqué fisiológico.",
    },
    {
        "topic": "Alternativas keto a los antojos dulces más comunes",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, con opciones concretas y realistas.",
    },
    {
        "topic": "Qué comer antes y después de entrenar siguiendo keto",
        "objective": "Este post debe ser 100% un tip o técnica realmente útil y accionable, enfocado en timing de comidas.",
    },
]


def next_topic(rotation_index: int) -> dict[str, str]:
    """Pure function: given the schedule's current index, return the topic
    to use and let the caller advance/persist the index — kept side-effect
    free so it's trivially testable."""
    return HEADLINE_TOPICS[rotation_index % len(HEADLINE_TOPICS)]
