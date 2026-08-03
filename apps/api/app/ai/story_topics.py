"""Rotating topic bank for app.workers.story_scheduler.

Theme: "TÚ DECIDES EL MENÚ" (2026-08-03, user-provided content strategy)
— every story invites the audience to choose, answer, or react in a few
seconds (a poll, an either/or, a short question, "guess the ingredient"),
never a tip explained end-to-end (that's Headline's job, and the whole
point of keeping Historias distinct is to not compete with it). Meta's
Graph API has no third-party way to attach native Instagram poll/slider
stickers to a Story — only the Instagram app itself can add those by
hand — so the "interaction" here is simulated in the caption text itself
(explicitly asking people to answer in the comments) rather than a real
interactive sticker.

Topics are grouped by weekday (Python's date.weekday(): 0=Monday) so a
given day's batch leans into one theme instead of anything-goes:

    Lunes      (0) — elección de menú
    Martes     (1) — esto o lo otro
    Miércoles  (2) — confesión o pregunta abierta
    Jueves     (3) — adivina el ingrediente
    Viernes    (4) — duelo de recetas
    Sábado     (5) — detrás de cámaras
    Domingo    (6) — votación de la receta de la semana

StorySchedule.topic_rotation_index still cycles through whichever day's
topics are in play, one entry at a time, so consecutive auto-stories on
the same day never repeat the same topic.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Appended to every topic's specific instruction — the shared "how to
# write it" rules from the content strategy, kept in one place instead
# of repeated in all 15 entries below.
INTERACTIVE_STYLE_GUIDE = (
    "Historia breve e interactiva: invita a elegir, responder u opinar en los "
    "comentarios (no hay encuestas/deslizadores nativos por API). Sin explicaciones "
    "largas, sin consejos extensos, sin promesas de pérdida de peso, nada tipo "
    "artículo. Título corto en MAYÚSCULAS, máx. dos líneas de apoyo, una sola "
    "interacción clara."
)

STORY_TOPICS: list[dict[str, object]] = [
    # Lunes — elección de menú
    {
        "day": 0,
        "topic": "¿QUÉ PREPARAMOS HOY? — Pollo al ajo 🐔 vs. Salmón cremoso 🐟",
        "objective": "Encuesta 'esto o lo otro' entre dos platos concretos — el título ES la pregunta, la interacción es votar por uno de los dos en los comentarios.",
    },
    {
        "day": 0,
        "topic": "ARMA TU CENA KETO — proteína + vegetal + salsa",
        "objective": "Invita a describir su combinación ideal de cena keto (proteína + vegetal + salsa) y a escribirla en los comentarios.",
    },
    # Martes — esto o lo otro
    {
        "day": 1,
        "topic": "ELIGE TU DESAYUNO — Huevos con aguacate 🥑 vs. Omelette con queso 🧀",
        "objective": "Encuesta 'esto o lo otro' entre dos desayunos keto concretos — votar por uno de los dos en los comentarios.",
    },
    {
        "day": 1,
        "topic": "¿DULCE O SALADO? — Postre keto 🍫 vs. Snack crujiente 🥓",
        "objective": "Encuesta 'esto o lo otro' entre antojo dulce y salado — votar por uno de los dos en los comentarios.",
    },
    {
        "day": 1,
        "topic": "¿COCINAS O PIDES COMIDA? — Cocino en casa vs. Busco algo rápido",
        "objective": "Encuesta 'esto o lo otro' sobre el hábito del día a día — votar por una de las dos opciones en los comentarios.",
    },
    # Miércoles — confesión o pregunta abierta
    {
        "day": 2,
        "topic": "CONFESIONES KETO — 'El alimento que más extraño es...'",
        "objective": "Pregunta abierta e íntima — invita a completar la frase en los comentarios, tono honesto y sin juicio.",
    },
    {
        "day": 2,
        "topic": "¿CUÁNDO TE DAN MÁS ANTOJOS? — En la tarde vs. En la noche",
        "objective": "Pregunta abierta y cómplice sobre el momento del día con más antojos — invita a responder en los comentarios.",
    },
    {
        "day": 2,
        "topic": "¿QUÉ INGREDIENTE NO PUEDE FALTAR? — Aguacate, Queso, Huevo o Pollo",
        "objective": "Pregunta abierta con varias opciones — invita a elegir su imprescindible y decirlo en los comentarios.",
    },
    # Jueves — adivina el ingrediente
    {
        "day": 3,
        "topic": "ADIVINA EL INGREDIENTE — muestra una silueta o parte del alimento",
        "objective": "Reto de adivinanza: describe brevemente una pista visual del ingrediente (sin decirlo) e invita a adivinar en los comentarios; la respuesta se revela en la próxima historia.",
    },
    {
        "day": 3,
        "topic": "¿CUÁL ELIMINARÍAS DEL PLATO? — Brócoli, Aguacate, Huevo o Queso",
        "objective": "Pregunta de elección forzada entre varios ingredientes de un plato — invita a decir cuál eliminaría en los comentarios.",
    },
    # Viernes — duelo de recetas
    {
        "day": 4,
        "topic": "DUELO DE SNACKS — Nueces 🥜 vs. Rollitos de queso 🧀",
        "objective": "Encuesta 'esto o lo otro' entre dos snacks keto — votar por uno de los dos en los comentarios.",
    },
    {
        "day": 4,
        "topic": "¿QUÉ RECETA QUIERES VER MAÑANA? — Pizza keto vs. Hamburguesa sin pan",
        "objective": "Encuesta sobre qué receta preparar después — votar por una de las dos opciones en los comentarios.",
    },
    # Sábado — detrás de cámaras
    {
        "day": 5,
        "topic": "DETRÁS DE LA RECETA — 'Estamos preparando algo nuevo, ¿qué crees que lleva?'",
        "objective": "Momento casual de detrás de cámaras — invita a adivinar el ingrediente sorpresa de la próxima receta en los comentarios.",
    },
    {
        "day": 5,
        "topic": "RETO DEL DÍA — 'Hoy intentaré evitar bebidas azucaradas'",
        "objective": "Reto sencillo del día — invita a unirse con un simple 'me uno' o 'lo intentaré' en los comentarios.",
    },
    # Domingo — votación de la receta de la semana
    {
        "day": 6,
        "topic": "CALIFICA ESTE PLATO — ¿cuánto se te antoja del 1 al 5?",
        "objective": "Invita a calificar el antojo que genera el plato de la semana del 1 al 5 en los comentarios, tono ligero y divertido.",
    },
]


def _topics_for_day(weekday: int) -> list[dict[str, object]]:
    day_topics = [t for t in STORY_TOPICS if t["day"] == weekday]
    return day_topics or STORY_TOPICS


def next_topic(rotation_index: int, *, weekday: int | None = None) -> dict[str, str]:
    """Pure function: given the schedule's current index (and optionally
    an explicit weekday for testability), return the topic to use and
    let the caller advance/persist the index — kept side-effect free so
    it's trivially testable. Defaults to today's real weekday (UTC) when
    not given, so a given day's batch leans into that day's theme."""
    if weekday is None:
        weekday = datetime.now(UTC).weekday()
    day_topics = _topics_for_day(weekday)
    return day_topics[rotation_index % len(day_topics)]
