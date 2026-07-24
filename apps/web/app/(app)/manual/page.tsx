"use client";

import Link from "next/link";
import {
  LayoutDashboard,
  CalendarDays,
  ClipboardCheck,
  Sparkles,
  Send,
  ImageIcon,
  Zap,
  Users,
  Link2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const SECTIONS = [
  { id: "modulos", label: "Módulos del sistema" },
  { id: "meta", label: "Conectar Facebook e Instagram" },
  { id: "cambiar-cuentas", label: "Cambiar entre cuentas" },
  { id: "roles", label: "Roles y permisos" },
];

export default function ManualPage() {
  return (
    <div className="grid gap-8 lg:grid-cols-[14rem_1fr]">
      <nav className="hidden lg:block">
        <div className="sticky top-8 space-y-1">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            En esta página
          </p>
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="block rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              {s.label}
            </a>
          ))}
        </div>
      </nav>

      <div className="max-w-3xl space-y-10">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Manual de RQT21 Growth OS</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Guía de uso del sistema: qué hace cada módulo y cómo conectar y cambiar
            entre cuentas reales de Facebook e Instagram.
          </p>
        </div>

        <section id="modulos" className="scroll-mt-6 space-y-4">
          <h2 className="text-lg font-semibold tracking-tight">Módulos del sistema</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <ModuleCard
              icon={LayoutDashboard}
              title="Dashboard"
              body="Métricas generales de campañas, contenido, leads, publicaciones y uso de IA de la organización activa."
            />
            <ModuleCard
              icon={CalendarDays}
              title="Calendario editorial"
              body="Planifica ítems de contenido por fecha, plataforma y prioridad; programa o marca como publicado manualmente."
            />
            <ModuleCard
              icon={ClipboardCheck}
              title="Revisiones"
              body="Bandeja de aprobación: enviar contenido a revisión, aprobar, pedir cambios o rechazar. Solo OWNER/ADMIN aprueban."
            />
            <ModuleCard
              icon={Sparkles}
              title="Generar (IA)"
              body="Genera texto (captions, guiones, ideas) o imágenes con IA a partir de un tema y la voz de marca. Nunca publica solo — siempre queda como borrador para revisión humana."
            />
            <ModuleCard
              icon={ImageIcon}
              title="Activos"
              body="Biblioteca de imágenes, videos y documentos. Guarda variantes por plataforma (historia, feed, etc.) y controla el texto alternativo."
            />
            <ModuleCard
              icon={Send}
              title="Publicaciones y Conexiones"
              body="Prepara, valida, programa y publica contenido en las cuentas conectadas (Facebook, Instagram, o manual). Ver la guía de Meta más abajo."
            />
            <ModuleCard
              icon={Zap}
              title="Automatizaciones"
              body="Plantillas predefinidas (ej. 'contenido aprobado → crear borrador de publicación'). Nunca ejecutan código libre ni publican sin revisión."
            />
            <ModuleCard
              icon={Users}
              title="Leads y Miembros"
              body="Pipeline de leads con atribución UTM, y gestión de miembros/roles de la organización."
            />
          </div>
        </section>

        <Separator />

        <section id="meta" className="scroll-mt-6 space-y-4">
          <div className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold tracking-tight">Conectar Facebook e Instagram</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            RQT21 publica en páginas reales de Facebook y cuentas de Instagram vinculadas
            a través de <strong>conexiones de publicación</strong>. Cada conexión guarda un
            token cifrado y nunca lo muestra completo — solo los últimos 4 caracteres, y
            solo a OWNER/ADMIN.
          </p>

          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-base">
                Opción recomendada: token base (se renueva solo)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Un token de página estático puede ser invalidado por Meta sin aviso. Para
                evitar eso, RQT21 soporta guardar un <strong>token base de larga duración</strong>{" "}
                (idealmente un <em>System User token</em> de Business Manager, que no expira solo)
                — el sistema resuelve automáticamente un token de página fresco en cada
                publicación, sin que tengas que volver a pegarlo nunca.
              </p>
              <ol className="list-decimal space-y-2 pl-5">
                <li>
                  En Meta Business Manager, ve a <strong>Usuarios del sistema</strong> y crea (o
                  usa) un usuario del sistema con acceso <strong>Admin</strong> a la página de
                  Facebook que quieres conectar.
                </li>
                <li>
                  Click <strong>Generar token</strong>, elige la app de Meta asociada, y marca
                  los permisos: <code className="rounded bg-muted px-1">pages_show_list</code>,{" "}
                  <code className="rounded bg-muted px-1">pages_read_engagement</code>,{" "}
                  <code className="rounded bg-muted px-1">pages_manage_posts</code>. Si vas a
                  publicar en Instagram, agrega también{" "}
                  <code className="rounded bg-muted px-1">instagram_basic</code> e{" "}
                  <code className="rounded bg-muted px-1">instagram_content_publish</code>.
                </li>
                <li>Copia el token generado — ese es tu token base.</li>
                <li>
                  En <Link href="/publishing/connections" className="text-primary hover:underline">
                    Publicaciones → Gestionar conexiones
                  </Link>, crea una nueva conexión: elige plataforma (Facebook o Instagram),
                  proveedor <strong>META</strong>, pon el <strong>ID de cuenta externa</strong>{" "}
                  (el ID de la página de Facebook, o el ID de la cuenta de Instagram si es
                  Instagram), pega el token en el campo de token, y marca la casilla{" "}
                  <strong>&quot;Es un token base de larga duración&quot;</strong>.
                </li>
                <li>
                  Click <strong>Verificar</strong> en la conexión recién creada — si todo está
                  bien, el estado cambia a <Badge variant="success" className="align-middle">ACTIVE</Badge>.
                </li>
              </ol>
              <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-warning">
                Nota para Instagram: la Graph API solo resuelve tokens contra el ID de la{" "}
                <strong>página de Facebook</strong>, no contra el ID de la cuenta de Instagram
                directamente. Por eso, al conectar Instagram con token base, el formulario
                muestra un campo extra: <strong>&quot;ID de la página de Facebook vinculada&quot;</strong>{" "}
                — complétalo con el ID de la página conectada a esa cuenta de Instagram.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-base">
                Alternativa: token de página estático
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Si solo quieres probar rápido en una página, puedes usar{" "}
                <a
                  href="https://developers.facebook.com/tools/explorer/"
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  Graph API Explorer
                </a>{" "}
                para generar un User Access Token con los mismos permisos, y luego llamar a{" "}
                <code className="rounded bg-muted px-1">
                  GET /me/accounts?fields=id,name,access_token,instagram_business_account
                </code>{" "}
                para obtener el Page Access Token directamente. Pégalo en el campo de token
                <strong> sin</strong> marcar la casilla de token base. Esta opción expira
                más rápido (semanas) y hay que repetirla manualmente cuando caduque.
              </p>
            </CardContent>
          </Card>
        </section>

        <Separator />

        <section id="cambiar-cuentas" className="scroll-mt-6 space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Cambiar entre cuentas</h2>
          <p className="text-sm text-muted-foreground">
            Puedes tener varias conexiones activas al mismo tiempo (distintas páginas de
            Facebook, distintas cuentas de Instagram, o incluso otra organización). En{" "}
            <Link href="/publishing/connections" className="text-primary hover:underline">
              Publicaciones → Conexiones
            </Link>{" "}
            verás todas las conexiones de la organización activa. Al preparar una
            publicación en <Link href="/publishing" className="text-primary hover:underline">
              Publicaciones
            </Link>, eliges a qué conexión se publica desde el selector &quot;Conexión&quot; del
            formulario — así puedes alternar entre cuentas sin reconectar nada.
          </p>
          <p className="text-sm text-muted-foreground">
            Para cambiar de <strong>organización</strong> completa (no solo de cuenta),
            usa el selector en la parte superior izquierda de cualquier pantalla.
          </p>
        </section>

        <Separator />

        <section id="roles" className="scroll-mt-6 space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Roles y permisos</h2>
          <div className="grid gap-2 text-sm">
            <RoleRow role="OWNER" desc="Acceso total: administra miembros, conexiones, aprueba contenido, publica." />
            <RoleRow role="ADMIN" desc="Igual que OWNER excepto cambios de facturación/organización de alto nivel." />
            <RoleRow role="MARKETER" desc="Crea y edita contenido, campañas, genera con IA, prepara publicaciones — no aprueba ni publica solo." />
            <RoleRow role="SALES" desc="Gestiona leads y su pipeline; puede exportar leads." />
            <RoleRow role="ANALYST" desc="Solo lectura de métricas y reportes." />
            <RoleRow role="VIEWER" desc="Solo lectura general, sin acceso a datos sensibles (PII de leads, tokens)." />
          </div>
        </section>
      </div>
    </div>
  );
}

function ModuleCard({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <Card>
      <CardContent className="flex gap-3 p-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{body}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function RoleRow({ role, desc }: { role: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-border p-3">
      <Badge variant="outline" className="shrink-0">{role}</Badge>
      <p className="text-muted-foreground">{desc}</p>
    </div>
  );
}

