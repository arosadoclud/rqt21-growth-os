"""Topic bank for app.workers.story_scheduler.

Theme: "TÚ DECIDES EL MENÚ" (2026-08-03, user-provided content strategy,
expanded 2026-08-03 to fight repetition) — every story invites the
audience to choose, answer, or react in a few seconds (a poll, an
either/or, a short question, "guess the ingredient"), never a tip
explained end-to-end (that's Headline's job, and the whole point of
keeping Historias distinct is to not compete with it). Meta's Graph API
has no third-party way to attach native Instagram poll/slider stickers
to a Story — only the Instagram app itself can add those by hand — so
the "interaction" here is simulated in the caption text itself
(explicitly asking people to answer in the comments) rather than a real
interactive sticker.

45 topics across 9 categories (5 each) — well over the 40-topic minimum
— tagged with a stable ``id`` plus optional ``pair``/``ingredients``
tuples so app.workers.story_scheduler can enforce real 7-day cooldowns
(never the same topic, answer-pair, or main ingredient twice within a
week) and same-day category variety (cycle through every category
before any repeats), instead of the old "one theme per weekday" scheme
this replaces.
"""

from __future__ import annotations

import re
import unicodedata

CATEGORIES: tuple[str, ...] = (
    "esto_o_lo_otro",
    "encuesta",
    "pregunta_abierta",
    "adivina_ingrediente",
    "califica_plato",
    "detras_camaras",
    "confesion",
    "reto",
    "eleccion_menu",
)

# Appended to every topic's specific instruction — the shared "how to
# write it" rules from the content strategy, kept in one place instead
# of repeated in every entry below.
INTERACTIVE_STYLE_GUIDE = (
    "Historia breve e interactiva: invita a elegir, responder u opinar en los "
    "comentarios (no hay encuestas/deslizadores nativos por API). Sin explicaciones "
    "largas, sin consejos extensos, sin promesas de pérdida de peso, nada tipo "
    "artículo. Título corto en MAYÚSCULAS, máx. dos líneas de apoyo, una sola "
    "interacción clara."
)

STORY_TOPICS: list[dict[str, object]] = [
    # esto_o_lo_otro
    {
        "id": "pollo_salmon",
        "category": "esto_o_lo_otro",
        "topic": "¿QUÉ PREPARAMOS HOY? Pollo al ajo 🐔 vs. Salmón cremoso 🐟",
        "objective": "Encuesta 'esto o lo otro' — votar por uno de los dos platos en los comentarios.",
        "pair": ("pollo", "salmon"),
        "ingredients": ("pollo", "salmon"),
    },
    {
        "id": "desayuno_huevo_omelette",
        "category": "esto_o_lo_otro",
        "topic": "ELIGE TU DESAYUNO: Huevos con aguacate 🥑 vs. Omelette con queso 🧀",
        "objective": "Encuesta 'esto o lo otro' entre dos desayunos keto — votar en los comentarios.",
        "pair": ("huevos con aguacate", "omelette con queso"),
        "ingredients": ("huevo", "queso", "aguacate"),
    },
    {
        "id": "dulce_salado",
        "category": "esto_o_lo_otro",
        "topic": "¿DULCE O SALADO? Postre keto 🍫 vs. Snack crujiente 🥓",
        "objective": "Encuesta 'esto o lo otro' entre antojo dulce y salado — votar en los comentarios.",
        "pair": ("dulce", "salado"),
    },
    {
        "id": "cocinar_pedir",
        "category": "esto_o_lo_otro",
        "topic": "¿COCINAS O PIDES COMIDA? Cocino en casa vs. Busco algo rápido",
        "objective": "Encuesta 'esto o lo otro' sobre el hábito del día a día — votar en los comentarios.",
        "pair": ("cocinar en casa", "pedir comida"),
    },
    {
        "id": "cafe_te",
        "category": "esto_o_lo_otro",
        "topic": "¿CAFÉ O TÉ? — ¿con qué arrancas el día?",
        "objective": "Encuesta 'esto o lo otro' para arrancar el día — votar en los comentarios.",
        "pair": ("cafe", "te"),
    },
    # encuesta (duelos)
    {
        "id": "duelo_snacks",
        "category": "encuesta",
        "topic": "DUELO DE SNACKS: Nueces 🥜 vs. Rollitos de queso 🧀",
        "objective": "Encuesta 'esto o lo otro' entre dos snacks keto — votar en los comentarios.",
        "pair": ("nueces", "rollitos de queso"),
        "ingredients": ("nueces", "queso"),
    },
    {
        "id": "duelo_postres",
        "category": "encuesta",
        "topic": "DUELO DE POSTRES: Cheesecake keto 🍰 vs. Mousse de chocolate 🍫",
        "objective": "Encuesta 'esto o lo otro' entre dos postres keto — votar en los comentarios.",
        "pair": ("cheesecake keto", "mousse de chocolate"),
    },
    {
        "id": "duelo_desayunos",
        "category": "encuesta",
        "topic": "DUELO DE DESAYUNOS: Waffles keto vs. Panqueques keto",
        "objective": "Encuesta 'esto o lo otro' entre dos desayunos keto — votar en los comentarios.",
        "pair": ("waffles keto", "panqueques keto"),
    },
    {
        "id": "proxima_receta",
        "category": "encuesta",
        "topic": "¿QUÉ RECETA QUIERES VER MAÑANA? Pizza keto vs. Hamburguesa sin pan",
        "objective": "Encuesta sobre qué receta preparar después — votar en los comentarios.",
        "pair": ("pizza keto", "hamburguesa sin pan"),
    },
    {
        "id": "acompanante",
        "category": "encuesta",
        "topic": "ELIGE EL ACOMPAÑANTE: Ensalada 🥗 vs. Puré de coliflor",
        "objective": "Encuesta 'esto o lo otro' de acompañante — votar en los comentarios.",
        "pair": ("ensalada", "pure de coliflor"),
    },
    # pregunta_abierta
    {
        "id": "ingrediente_imprescindible",
        "category": "pregunta_abierta",
        "topic": "¿QUÉ INGREDIENTE NO PUEDE FALTAR? Aguacate, queso, huevo o pollo",
        "objective": "Pregunta abierta con varias opciones — invita a elegir su imprescindible en los comentarios.",
        "ingredients": ("aguacate", "queso", "huevo", "pollo"),
    },
    {
        "id": "momento_antojo",
        "category": "pregunta_abierta",
        "topic": "¿CUÁNDO TE DAN MÁS ANTOJOS? En la tarde vs. en la noche",
        "objective": "Pregunta abierta y cómplice sobre el momento del día con más antojos — responder en los comentarios.",
        "pair": ("tarde", "noche"),
    },
    {
        "id": "motivo_empezar",
        "category": "pregunta_abierta",
        "topic": "¿QUÉ TE MOTIVÓ A EMPEZAR KETO? Cuéntanos tu razón",
        "objective": "Pregunta abierta sobre su motivación — invita a compartirla en los comentarios.",
    },
    {
        "id": "reto_dificil",
        "category": "pregunta_abierta",
        "topic": "LO MÁS DIFÍCIL DE EMPEZAR KETO — cuéntanos en los comentarios",
        "objective": "Pregunta abierta y honesta sobre lo más difícil de empezar — responder en los comentarios.",
    },
    {
        "id": "entrenar_comer",
        "category": "pregunta_abierta",
        "topic": "¿ENTRENAS ANTES O DESPUÉS DE COMER?",
        "objective": "Pregunta abierta sobre su rutina — responder en los comentarios.",
        "pair": ("antes de comer", "despues de comer"),
    },
    # adivina_ingrediente
    {
        "id": "adivina_silueta",
        "category": "adivina_ingrediente",
        "topic": "ADIVINA EL INGREDIENTE — muestra una silueta o parte del alimento",
        "objective": "Reto de adivinanza: describe una pista visual del ingrediente (sin decirlo) — invita a adivinar en los comentarios.",
    },
    {
        "id": "adivina_receta",
        "category": "adivina_ingrediente",
        "topic": "ADIVINA LA RECETA — con estos 3 ingredientes, ¿qué se cocina?",
        "objective": "Reto de adivinanza con 3 ingredientes — invita a adivinar la receta en los comentarios.",
    },
    {
        "id": "que_es_esto",
        "category": "adivina_ingrediente",
        "topic": "¿QUÉ ES ESTO? — primer plano misterioso de un ingrediente keto",
        "objective": "Reto de adivinanza con primer plano misterioso — invita a adivinar en los comentarios.",
    },
    {
        "id": "elimina_plato",
        "category": "adivina_ingrediente",
        "topic": "¿CUÁL ELIMINARÍAS DEL PLATO? Brócoli, aguacate, huevo o queso",
        "objective": "Elección forzada entre ingredientes de un plato — invita a decir cuál eliminaría en los comentarios.",
        "ingredients": ("brocoli", "aguacate", "huevo", "queso"),
    },
    {
        "id": "adivina_condimento",
        "category": "adivina_ingrediente",
        "topic": "ADIVINA EL CONDIMENTO SECRETO — huele, no se ve",
        "objective": "Reto de adivinanza por aroma — invita a adivinar el condimento en los comentarios.",
    },
    # califica_plato
    {
        "id": "califica_antojo",
        "category": "califica_plato",
        "topic": "CALIFICA ESTE PLATO — ¿cuánto se te antoja del 1 al 5?",
        "objective": "Invita a calificar el antojo del 1 al 5 en los comentarios, tono ligero.",
    },
    {
        "id": "califica_dificultad",
        "category": "califica_plato",
        "topic": "¿QUÉ TAN FÁCIL TE PARECE ESTA RECETA? del 1 al 5",
        "objective": "Invita a calificar qué tan fácil parece la receta del 1 al 5 en los comentarios.",
    },
    {
        "id": "califica_semana",
        "category": "califica_plato",
        "topic": "¿QUÉ TE GUSTÓ MÁS ESTA SEMANA? — cuéntanos tu favorito",
        "objective": "Invita a nombrar su plato favorito de la semana en los comentarios.",
    },
    {
        "id": "califica_textura",
        "category": "califica_plato",
        "topic": "CALIFICA LA TEXTURA — ¿crujiente, cremoso o ambos? del 1 al 5",
        "objective": "Invita a calificar la textura del plato del 1 al 5 en los comentarios.",
    },
    {
        "id": "califica_sabor",
        "category": "califica_plato",
        "topic": "CALIFICA EL SABOR — ¿le subimos o bajamos la sal? del 1 al 5",
        "objective": "Invita a calificar el sabor y opinar sobre la sal del 1 al 5 en los comentarios.",
    },
    # detras_camaras
    {
        "id": "detras_receta",
        "category": "detras_camaras",
        "topic": "DETRÁS DE LA RECETA — 'Estamos preparando algo nuevo, ¿qué crees que lleva?'",
        "objective": "Momento casual de detrás de cámaras — invita a adivinar el ingrediente sorpresa en los comentarios.",
    },
    {
        "id": "dia_cocina",
        "category": "detras_camaras",
        "topic": "UN DÍA EN NUESTRA COCINA — ¿qué crees que estamos preparando?",
        "objective": "Momento casual de cocina — invita a adivinar qué se prepara en los comentarios.",
    },
    {
        "id": "detras_foto",
        "category": "detras_camaras",
        "topic": "DETRÁS DE LA FOTO — así se ve antes de quedar perfecto",
        "objective": "Momento casual y honesto de detrás de cámaras — invita a reaccionar en los comentarios.",
    },
    {
        "id": "preparando_semana",
        "category": "detras_camaras",
        "topic": "PREPARANDO LA SEMANA — ¿qué receta crees que viene?",
        "objective": "Momento casual de planificación — invita a adivinar la próxima receta en los comentarios.",
    },
    {
        "id": "ingrediente_secreto",
        "category": "detras_camaras",
        "topic": "EL INGREDIENTE SECRETO DE HOY — ¿lo adivinas?",
        "objective": "Momento casual con un ingrediente sorpresa — invita a adivinarlo en los comentarios.",
    },
    # confesion
    {
        "id": "confesion_extrano",
        "category": "confesion",
        "topic": "CONFESIONES KETO — 'El alimento que más extraño es...'",
        "objective": "Pregunta abierta e íntima — invita a completar la frase en los comentarios, tono honesto.",
    },
    {
        "id": "confesion_recaida",
        "category": "confesion",
        "topic": "CONFESIONES KETO — 'La vez que se me antojó y...'",
        "objective": "Confesión honesta sobre un antojo — invita a completar la frase en los comentarios.",
    },
    {
        "id": "confesion_dificil",
        "category": "confesion",
        "topic": "CONFESIONES KETO — 'Lo más difícil de mi semana fue...'",
        "objective": "Confesión honesta sobre la semana — invita a completar la frase en los comentarios.",
    },
    {
        "id": "confesion_logro",
        "category": "confesion",
        "topic": "CONFESIONES KETO — 'Mi pequeña victoria de hoy fue...'",
        "objective": "Confesión honesta y positiva — invita a compartir su victoria en los comentarios.",
    },
    {
        "id": "confesion_antojo_secreto",
        "category": "confesion",
        "topic": "CONFESIONES KETO — 'Mi antojo secreto (no keto) es...'",
        "objective": "Confesión honesta y divertida sin juicio — invita a completar la frase en los comentarios.",
    },
    # reto
    {
        "id": "reto_azucar",
        "category": "reto",
        "topic": "RETO DEL DÍA — 'Hoy intentaré evitar bebidas azucaradas'",
        "objective": "Reto sencillo — invita a unirse con 'me uno' o 'lo intentaré' en los comentarios.",
    },
    {
        "id": "reto_agua",
        "category": "reto",
        "topic": "RETO DEL DÍA — 'Hoy tomaré más agua de lo normal'",
        "objective": "Reto sencillo — invita a unirse con 'me uno' o 'lo intentaré' en los comentarios.",
    },
    {
        "id": "reto_sin_harina",
        "category": "reto",
        "topic": "RETO DEL FIN DE SEMANA — 'Hoy cocino sin harina ni azúcar'",
        "objective": "Reto sencillo — invita a unirse con 'me uno' o 'lo intentaré' en los comentarios.",
    },
    {
        "id": "reto_snack",
        "category": "reto",
        "topic": "RETO DEL DÍA — 'Hoy cambio el snack de siempre por uno keto'",
        "objective": "Reto sencillo — invita a unirse con 'me uno' o 'lo intentaré' en los comentarios.",
    },
    {
        "id": "reto_meal_prep",
        "category": "reto",
        "topic": "RETO DEL DÍA — 'Hoy preparo algo de comida para mañana'",
        "objective": "Reto sencillo — invita a unirse con 'me uno' o 'lo intentaré' en los comentarios.",
    },
    # eleccion_menu
    {
        "id": "que_preparamos_manana",
        "category": "eleccion_menu",
        "topic": "¿QUÉ PREPARAMOS MAÑANA? Elige entre dos opciones del recetario",
        "objective": "Encuesta sobre el menú de mañana — votar en los comentarios.",
    },
    {
        "id": "arma_cena",
        "category": "eleccion_menu",
        "topic": "ARMA TU CENA KETO — proteína + vegetal + salsa",
        "objective": "Invita a describir su combinación ideal de cena keto y escribirla en los comentarios.",
    },
    {
        "id": "arma_almuerzo",
        "category": "eleccion_menu",
        "topic": "ARMA TU ALMUERZO KETO — proteína + vegetal + grasa saludable",
        "objective": "Invita a describir su combinación ideal de almuerzo keto y escribirla en los comentarios.",
    },
    {
        "id": "elige_proteina",
        "category": "eleccion_menu",
        "topic": "¿QUÉ PROTEÍNA ELIGES HOY? Res 🥩 vs. pescado 🐟",
        "objective": "Encuesta 'esto o lo otro' entre dos proteínas — votar en los comentarios.",
        "pair": ("res", "pescado"),
        "ingredients": ("res", "pescado"),
    },
    {
        "id": "vota_semana",
        "category": "eleccion_menu",
        "topic": "LA RECETA DE LA SEMANA — vota cuál quieres ver primero",
        "objective": "Encuesta sobre qué receta publicar primero esta semana — votar en los comentarios.",
    },
]


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, strip emoji/punctuation, collapse
    whitespace — used everywhere duplicate/cooldown detection needs to
    treat 'POLLO 🐔 vs. Salmón!' and 'pollo vs salmon' as the same
    thing."""
    text = (text or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def pair_key(pair: tuple[str, ...] | None) -> str | None:
    """Order-independent key for a topic's answer pair — 'pollo o salmón'
    and 'salmón o pollo' must cooldown as the same pair."""
    if not pair:
        return None
    return "|".join(sorted(normalize_text(p) for p in pair))


def ingredients_key(ingredients: tuple[str, ...] | None) -> str | None:
    if not ingredients:
        return None
    return "|".join(sorted(normalize_text(i) for i in ingredients))
