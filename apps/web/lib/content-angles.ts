// Preset "content angles" for AI text generation — each maps to a canned
// instruction appended to GenerationInput.notes, which already flows
// straight into the <user_input> block the AI sees (see app/ai/prompts.py).
// Purely a frontend convenience: no backend changes needed, since `notes`
// already exists and is free text.
export type ContentAngle = "RECETA" | "CURIOSIDAD" | "REFLEXION" | "VALOR" | "VENTA";

export const CONTENT_ANGLES: { value: ContentAngle; label: string; hint: string; instruction: string }[] = [
  {
    value: "RECETA",
    label: "Receta",
    hint: "Presenta una receta puntual",
    instruction:
      "Escribe un titular y contenido enfocado en presentar esta receta específica, destacando " +
      "sus ingredientes o pasos clave de forma atractiva y apetitosa.",
  },
  {
    value: "CURIOSIDAD",
    label: "Curiosidad",
    hint: "Dato o pregunta que engancha",
    instruction:
      "Escribe un titular tipo curiosidad o dato interesante relacionado con nutrición o cocina " +
      "saludable, que genere intriga y ganas de seguir leyendo — no reveles todo en el titular.",
  },
  {
    value: "REFLEXION",
    label: "Reflexión",
    hint: "Cercano, sobre hábitos",
    instruction:
      "Escribe un titular y contenido tipo reflexión sobre la relación con la comida, los hábitos " +
      "alimenticios o el proceso de cambio — tono cercano y emocional, no solo informativo.",
  },
  {
    value: "VALOR",
    label: "Aportar valor",
    hint: "Tip útil, sin vender",
    instruction:
      "Escribe un titular y contenido que aporte un tip, técnica o información útil y accionable " +
      "sobre cocina saludable, sin promocionar nada — el valor real es lo que engancha.",
  },
  {
    value: "VENTA",
    label: "Venta del recetario",
    hint: "CTA al recetario / plan 21 días",
    instruction:
      "Escribe un titular y contenido orientado a promocionar el recetario de 120 recetas y el " +
      "plan de 21 días de RQT21, con un llamado a la acción claro para conocer más en " +
      "recetasquetransforman21.com o comentar \"INFO\".",
  },
];
