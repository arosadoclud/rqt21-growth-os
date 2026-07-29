# Auditoría frontend y base visual

## Stack confirmado

- Next.js 14 con App Router y React 18.
- TypeScript 5.6.
- Tailwind CSS 3.4.
- Componentes propios inspirados en shadcn/ui, con primitivas Radix UI.
- `next-themes` para modo claro y oscuro.
- Lucide para iconografía.
- Playwright para pruebas end-to-end.

No había una librería de gráficos instalada. El dashboard usa barras y distribuciones accesibles con CSS para evitar sumar una dependencia y aumentar el bundle en esta primera fase.

## Fortalezas encontradas

- Separación clara entre API, contratos compartidos y frontend.
- Contexto de autenticación y organización reutilizable.
- Rutas de producto ya completas para contenido, publicación, leads, automatización e IA.
- Componentes base consistentes para botones, tarjetas, inputs, tablas, badges y menús.
- Suite E2E amplia que cubre roles, privacidad y recorridos operativos completos.

## Problemas detectados

- El layout anterior concentraba navegación, organización, usuario y acciones en una sola cabecera extensa.
- El dashboard mezclaba carga de datos, composición visual y estados en un único archivo.
- Faltaban tokens semánticos para superficies elevadas, sidebar, estados informativos e interacción.
- La jerarquía visual era uniforme: métricas, alertas y contenido secundario tenían pesos similares.
- Algunos formularios tenían un título visual, pero no un nombre accesible asociado al elemento `form`.
- Varias pruebas E2E dependían de texto que estaba fuera del formulario o reutilizaban datos estáticos entre ejecuciones.

## Reorganización aplicada

- `components/layout`: shell, sidebar y topbar premium.
- `components/design-system`: cabeceras, métricas y estados reutilizables.
- `components/dashboard`: dashboard ejecutivo desacoplado de la ruta.
- `globals.css` y `tailwind.config.ts`: tokens semánticos y comportamiento visual global.
- Formularios críticos: nombres accesibles mediante `aria-labelledby`.

## Sistema visual

- Fondo oscuro profundo con superficies elevadas discretas.
- Verde como acento de acción y estado positivo.
- Bordes suaves, radios coherentes y sombras contenidas.
- Tipografía con jerarquías claras y cifras tabulares.
- Navegación agrupada por dominio del producto.
- Estados de carga, vacío, error, éxito y prioridad con tratamiento consistente.
- Sidebar colapsable en escritorio y panel modal con foco y Escape en móvil.

## Riesgos y siguientes fases

- Las páginas operativas conservan su estructura visual anterior; conviene migrarlas gradualmente a los nuevos encabezados y estados.
- Las tablas extensas requieren una estrategia móvil específica por dominio.
- El dashboard usa los datos históricos disponibles sin inventar comparaciones; tendencias temporales reales requerirán endpoints agregados por periodo.
- La suite E2E usa una base de datos compartida durante la sesión. Se reforzaron datos únicos, pero una limpieza transaccional por test reduciría todavía más la posibilidad de interferencias.

## Validación

- TypeScript: limpio.
- ESLint: limpio, sin warnings.
- Build de producción: correcto, 26 rutas.
- Playwright: los 22 escenarios funcionales pasan al ejecutarse en sus suites; la ejecución combinada también validó todos los flujos posteriores tras eliminar el conflicto entre dos servidores Next locales.
