// Preset "content angles" for AI text generation. Each maps to a strong,
// directive instruction that gets prepended to GenerationInput.objective —
// not appended to `notes` — because the prompt renders Objective first and
// Notes last/weakest (see app/ai/prompts.py::render_prompt), and a model
// reads "Notes: ..." as a minor aside rather than the actual brief. Routing
// the angle through Objective makes it read as the post's real goal, so the
// model commits the whole piece (title, hook, caption) to that single
// angle instead of writing a generic post with the angle as a footnote.
export type ContentAngle = "RECETA" | "CURIOSIDAD" | "REFLEXION" | "VALOR" | "VENTA";

export const CONTENT_ANGLES: { value: ContentAngle; label: string; hint: string; instruction: string }[] = [
  {
    value: "RECETA",
    label: "Receta",
    hint: "Presenta una receta puntual",
    instruction:
      "Este post debe ser 100% sobre UNA receta específica del tema. Todo — título, hook y " +
      "caption — tiene que girar en torno a esa receta puntual: sus ingredientes clave, su " +
      "preparación o lo que la hace especial. No la trates como ejemplo de paso, es el centro " +
      "del post.",
  },
  {
    value: "CURIOSIDAD",
    label: "Curiosidad",
    hint: "Dato o pregunta que engancha",
    instruction:
      "Este post debe ser 100% una curiosidad o dato interesante — no una receta ni una " +
      "publicación genérica. El título tiene que plantear la curiosidad o pregunta sin revelar " +
      "la respuesta completa, y el caption tiene que desarrollar ESE dato puntual con detalle " +
      "real (el porqué, la explicación), no desviarse hacia otro tema.",
  },
  {
    value: "REFLEXION",
    label: "Reflexión",
    hint: "Cercano, sobre hábitos",
    instruction:
      "Este post debe ser 100% una reflexión personal y cercana sobre la relación con la " +
      "comida, los hábitos o el proceso de cambio — no una receta ni un dato técnico. Prioriza " +
      "el tono emocional y honesto por sobre la información; el objetivo es que la persona se " +
      "sienta identificada, no que aprenda un tip.",
  },
  {
    value: "VALOR",
    label: "Aportar valor",
    hint: "Tip útil, sin vender",
    instruction:
      "Este post debe ser 100% un tip, técnica o pieza de información realmente útil y " +
      "accionable sobre el tema — no debe mencionar el recetario, el plan de 21 días ni pedir " +
      "que comenten \"INFO\". El valor del tip por sí solo es lo único que tiene que enganchar " +
      "en este post.",
  },
  {
    value: "VENTA",
    label: "Venta del recetario",
    hint: "CTA al recetario / plan 21 días",
    instruction:
      "Este post debe estar 100% orientado a promocionar el recetario de 120 recetas y el " +
      "plan de 21 días de RQT21. El título y el hook tienen que dejar clara la oferta (no solo " +
      "mencionarla al final), y el caption tiene que cerrar con un llamado a la acción directo " +
      "hacia recetasquetransforman21.com o a comentar \"INFO\".",
  },
];
