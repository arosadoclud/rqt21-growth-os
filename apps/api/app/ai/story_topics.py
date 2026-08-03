"""Rotating topic bank for app.workers.story_scheduler.

Deliberately different in kind from app.ai.headline_topics: Headline posts
are evergreen tips/curiosities meant to sit in the feed; Historias are
short, disposable (24h), conversational prompts meant to get a reaction
from a follower who's mid-scroll — a question, a poll-style either/or, a
behind-the-scenes moment, a quick "you too?" — not an article. Every
objective below explicitly asks for 1-2 short sentences plus a direct
question or prompt, never a tip explained end-to-end (that's Headline's
job).

StorySchedule.topic_rotation_index cycles through this list one entry at
a time so consecutive auto-stories never repeat the same topic or angle.
"""

from __future__ import annotations

STORY_TOPICS: list[dict[str, str]] = [
    {
        "topic": "Pregúntale a la comunidad qué proteína prefieren para cocinar hoy: pollo o salmón",
        "objective": "Historia de 1-2 frases muy cortas planteando la pregunta como una encuesta 'esto o lo otro' — nada de explicación, solo la pregunta y una razón mínima para responder.",
    },
    {
        "topic": "Comparte un momento cotidiano de estar cocinando keto en la casa",
        "objective": "Historia de 1-2 frases, tono cercano y casual como si le hablaras a un amigo mientras cocinas — termina con una pregunta directa a quien la ve.",
    },
    {
        "topic": "¿Café con crema o café solo en la mañana keto?",
        "objective": "Historia de 1-2 frases planteando la disyuntiva como encuesta 'esto o lo otro' — corta, directa, sin explicar nada más.",
    },
    {
        "topic": "Pregunta si alguien más se le antoja algo dulce a media tarde en keto",
        "objective": "Historia de 1-2 frases, tono de complicidad ('¿a ti también te pasa...?') — termina invitando a responder o reaccionar.",
    },
    {
        "topic": "Comparte una pequeña victoria del día siguiendo keto",
        "objective": "Historia de 1-2 frases, tono personal y honesto, sin sonar a logro perfecto — cierra preguntando cuál fue la victoria de quien la ve hoy.",
    },
    {
        "topic": "¿Ensalada o sopa como acompañante en la cena keto?",
        "objective": "Historia de 1-2 frases planteando la disyuntiva como encuesta 'esto o lo otro' — corta, directa, sin explicar nada más.",
    },
    {
        "topic": "Pregunta qué snack keto no puede faltar en la cartera o el carro",
        "objective": "Historia de 1-2 frases, tono curioso, invitando a responder con su snack favorito.",
    },
    {
        "topic": "Comparte lo que se siente pasar de sentirse hinchado a sentirse liviano con keto",
        "objective": "Historia de 1-2 frases, tono íntimo y honesto sobre cómo se siente el cuerpo — termina preguntando si a alguien más le ha pasado.",
    },
    {
        "topic": "¿Aguacate a cucharadas o en guacamole?",
        "objective": "Historia de 1-2 frases planteando la disyuntiva como encuesta 'esto o lo otro' — corta, directa, sin explicar nada más.",
    },
    {
        "topic": "Pregunta cuál es el reto más grande de seguir keto en reuniones familiares",
        "objective": "Historia de 1-2 frases, tono empático, reconociendo que es difícil — invita a compartir su experiencia.",
    },
    {
        "topic": "Comparte un detrás de cámaras de estar armando el contenido de la comunidad",
        "objective": "Historia de 1-2 frases, tono cercano tipo 'esto es lo que hacemos hoy detrás de cámaras' — cierra con una pregunta ligera a la audiencia.",
    },
    {
        "topic": "¿Nueces o queso como snack keto de media mañana?",
        "objective": "Historia de 1-2 frases planteando la disyuntiva como encuesta 'esto o lo otro' — corta, directa, sin explicar nada más.",
    },
    {
        "topic": "Pregunta si alguien más cocina de más los domingos para toda la semana",
        "objective": "Historia de 1-2 frases, tono cómplice ('¿tú también?') — invita a responder sí o no.",
    },
    {
        "topic": "Comparte un recordatorio breve de que ir despacio también cuenta como progreso",
        "objective": "Historia de 1-2 frases, tono cálido y motivador sin sonar a frase genérica de calendario — cierra preguntando cómo va la semana de quien la ve.",
    },
]


def next_topic(rotation_index: int) -> dict[str, str]:
    """Pure function: given the schedule's current index, return the
    topic to use and let the caller advance/persist the index — kept
    side-effect free so it's trivially testable."""
    return STORY_TOPICS[rotation_index % len(STORY_TOPICS)]
