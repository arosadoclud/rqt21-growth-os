"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  AtSign,
  Building2,
  CalendarDays,
  ExternalLink,
  FileText,
  Info,
  MapPin,
  MessageCircle,
  Plus,
  RefreshCw,
  Route,
  UserRound,
} from "lucide-react";
import type {
  Brand,
  Campaign,
  ContentItem,
  Lead,
  LeadActivity,
  LeadActivityType,
  LeadStatus,
  Product,
  TrackingLink,
} from "@rqt21/contracts";
import { LEAD_STATUSES } from "@rqt21/contracts";

import { PageHeader } from "@/components/design-system/page-header";
import { StatusBadge } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

import {
  ACTIVITY_ICONS,
  ACTIVITY_LABELS,
  ACTIVITY_OPTIONS,
  activityDescription,
  formatLeadDate,
  leadName,
  LEAD_SOURCE_LABELS,
  LEAD_STATUS_LABELS,
  LEAD_STATUS_TONES,
} from "./lead-config";

export function LeadProfile({ leadId }: { leadId: string }) {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = ["OWNER", "ADMIN", "SALES", "MARKETER"].includes(organization?.role ?? "");
  const canSeePii = canWrite;

  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [trackingLinks, setTrackingLinks] = useState<TrackingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activityType, setActivityType] = useState<LeadActivityType>("NOTE_ADDED");
  const [activityText, setActivityText] = useState("");

  const load = useCallback(async () => {
    if (!currentOrgId || !leadId) return;
    setLoading(true);
    setError(null);
    try {
      const [leadRow, activityRows, brandRows, campaignRows, productRows, contentRows, linkRows] =
        await Promise.all([
          api.getLead(currentOrgId, leadId),
          api.listLeadActivities(currentOrgId, leadId),
          api.listBrands(currentOrgId).catch(() => []),
          api.listCampaigns(currentOrgId).catch(() => []),
          api.listProducts(currentOrgId).catch(() => []),
          api.listContent(currentOrgId).catch(() => []),
          api.listTrackingLinks(currentOrgId).catch(() => []),
        ]);
      setLead(leadRow);
      setActivities(activityRows);
      setBrands(brandRows);
      setCampaigns(campaignRows);
      setProducts(productRows);
      setContents(contentRows);
      setTrackingLinks(linkRows);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.detail : "No pudimos cargar el lead.");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, leadId]);

  useEffect(() => {
    void load();
  }, [load]);

  const changeStatus = async (status: LeadStatus) => {
    if (!currentOrgId || !lead || lead.status === status) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await api.changeLeadStatus(currentOrgId, lead.id, status);
      setSuccess(`Estado actualizado a ${LEAD_STATUS_LABELS[status].toLowerCase()}.`);
      await load();
    } catch (changeError) {
      setError(changeError instanceof ApiError ? changeError.detail : "No pudimos cambiar el estado.");
    } finally {
      setBusy(false);
    }
  };

  const addActivity = async () => {
    if (!currentOrgId || !lead || !activityText.trim()) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await api.createLeadActivity(currentOrgId, lead.id, {
        activity_type: activityType,
        description: activityText.trim(),
      });
      setActivityText("");
      setSuccess("Actividad añadida al historial.");
      await load();
    } catch (activityError) {
      setError(activityError instanceof ApiError ? activityError.detail : "No pudimos añadir la actividad.");
    } finally {
      setBusy(false);
    }
  };

  const attribution = useMemo(
    () => ({
      brand: brands.find((item) => item.id === lead?.brand_id)?.name,
      campaign: campaigns.find((item) => item.id === lead?.campaign_id)?.name,
      product: products.find((item) => item.id === lead?.product_id)?.name,
      content: contents.find((item) => item.id === lead?.content_item_id)?.title,
      tracking: trackingLinks.find((item) => item.id === lead?.tracking_link_id)?.short_code,
    }),
    [brands, campaigns, contents, lead, products, trackingLinks],
  );

  if (!currentOrgId) {
    return <StatePanel title="Selecciona una organización" description="El detalle aparecerá cuando elijas una organización." />;
  }
  if (loading && !lead) {
    return <Card><CardContent className="p-5"><LoadingSkeleton rows={7} /></CardContent></Card>;
  }
  if (!lead) {
    return (
      <StatePanel
        title="Lead no encontrado"
        description={error ?? "Este lead ya no está disponible."}
        actionLabel="Volver a Leads"
        onAction={() => window.location.assign("/leads")}
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Detalle del lead"
        title={leadName(lead)}
        description={`${lead.public_id} · ${LEAD_SOURCE_LABELS[lead.source]}`}
        metadata={
          <>
            <StatusBadge label={LEAD_STATUS_LABELS[lead.status]} tone={LEAD_STATUS_TONES[lead.status]} />
            <span className="text-xs text-muted-foreground">
              Actualizado {formatLeadDate(lead.updated_at)}
            </span>
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link href="/leads"><ArrowLeft className="h-4 w-4" />Volver</Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Actualizar
            </Button>
          </>
        }
      />

      {(error || success) && (
        <div
          role={error ? "alert" : "status"}
          className={cn(
            "rounded-xl border px-4 py-3 text-sm",
            error ? "border-destructive/25 bg-destructive/8 text-destructive" : "border-success/25 bg-success/8 text-success",
          )}
        >
          {error ?? success}
        </div>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <Card className="bg-card/85 shadow-none">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Route className="h-4 w-4 text-primary" />
                Etapa comercial
              </CardTitle>
              <p className="text-sm text-muted-foreground">Actualiza la etapa para mantener el pipeline al día.</p>
            </CardHeader>
            <CardContent>
              {canWrite ? (
                <div className="flex flex-wrap gap-2">
                  {LEAD_STATUSES.map((status) => (
                    <Button
                      key={status}
                      size="sm"
                      variant={lead.status === status ? "default" : "outline"}
                      disabled={busy || lead.status === status}
                      onClick={() => void changeStatus(status)}
                    >
                      {LEAD_STATUS_LABELS[status]}
                    </Button>
                  ))}
                </div>
              ) : (
                <PermissionNotice>Tu rol permite consultar el pipeline, pero no cambiar etapas.</PermissionNotice>
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/85 shadow-none">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <UserRound className="h-4 w-4 text-primary" />
                Contacto
              </CardTitle>
            </CardHeader>
            <CardContent>
              {canSeePii ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <ContactLink icon={AtSign} label="Correo" value={lead.email} href={lead.email ? `mailto:${lead.email}` : undefined} />
                  <ContactLink icon={MessageCircle} label="WhatsApp" value={lead.whatsapp} href={lead.whatsapp ? `https://wa.me/${lead.whatsapp.replace(/[^\d]/g, "")}` : undefined} external />
                  <ContactLink icon={UserRound} label="Teléfono" value={lead.phone} href={lead.phone ? `tel:${lead.phone}` : undefined} />
                  <ContactLink icon={MapPin} label="Ubicación" value={[lead.city, lead.country].filter(Boolean).join(", ") || null} />
                </div>
              ) : (
                <PermissionNotice>Los datos personales están protegidos para tu rol.</PermissionNotice>
              )}
              {canSeePii && lead.notes && (
                <div className="mt-4 rounded-xl border border-border bg-interactive/30 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Notas generales</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">{lead.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {canWrite && (
            <Card className="bg-card/85 shadow-none">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Plus className="h-4 w-4 text-primary" />
                  Registrar actividad
                </CardTitle>
                <p className="text-sm text-muted-foreground">Documenta el siguiente contacto o una nota para el equipo.</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <Select
                  value={activityType}
                  onChange={(event) => setActivityType(event.target.value as LeadActivityType)}
                  aria-label="Tipo de actividad"
                >
                  {ACTIVITY_OPTIONS.map((type) => (
                    <option key={type} value={type}>{ACTIVITY_LABELS[type]}</option>
                  ))}
                </Select>
                <Textarea
                  value={activityText}
                  onChange={(event) => setActivityText(event.target.value)}
                  rows={4}
                  placeholder="Resultado del contacto, acuerdos o próximos pasos…"
                  aria-label="Descripción de la actividad"
                />
                <Button onClick={() => void addActivity()} disabled={busy || !activityText.trim()}>
                  Añadir actividad
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card className="bg-card/85 shadow-none">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Building2 className="h-4 w-4 text-primary" />
                Atribución
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <DetailRow label="Marca" value={attribution.brand} />
                <DetailRow label="Producto" value={attribution.product} />
                <DetailRow label="Campaña" value={attribution.campaign} />
                <DetailRow label="Contenido" value={attribution.content} />
                <DetailRow label="Enlace de tracking" value={attribution.tracking} />
              </dl>
            </CardContent>
          </Card>

          <Card className="bg-card/85 shadow-none">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText className="h-4 w-4 text-primary" />
                Datos de adquisición
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <DetailRow label="UTM source" value={lead.utm_source} />
                <DetailRow label="UTM medium" value={lead.utm_medium} />
                <DetailRow label="UTM campaign" value={lead.utm_campaign} />
                <DetailRow label="UTM content" value={lead.utm_content} />
                <DetailRow label="UTM term" value={lead.utm_term} />
              </dl>
            </CardContent>
          </Card>
        </div>
      </section>

      <Card className="overflow-hidden bg-card/85 shadow-none">
        <CardHeader className="border-b border-border">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4 text-primary" />
            Historial del lead
          </CardTitle>
          <p className="text-sm text-muted-foreground">{activities.length} eventos registrados, del más reciente al más antiguo.</p>
        </CardHeader>
        <CardContent className="p-0">
          {activities.length === 0 ? (
            <StatePanel compact title="Sin actividad" description="Las notas y cambios de estado aparecerán aquí." className="m-4" />
          ) : (
            <ol className="divide-y divide-border">
              {activities.map((activity) => {
                const Icon = ACTIVITY_ICONS[activity.activity_type];
                return (
                  <li key={activity.id} className="relative flex gap-4 px-5 py-4 sm:px-6">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-interactive text-primary">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-sm font-semibold text-foreground">{ACTIVITY_LABELS[activity.activity_type]}</p>
                        <time className="text-xs text-muted-foreground">{formatLeadDate(activity.created_at)}</time>
                      </div>
                      {activityDescription(activity) ? (
                        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{activityDescription(activity)}</p>
                      ) : (
                        <p className="mt-1 text-sm italic text-muted-foreground">Detalle protegido o no disponible.</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ContactLink({
  icon: Icon,
  label,
  value,
  href,
  external,
}: {
  icon: typeof AtSign;
  label: string;
  value: string | null;
  href?: string;
  external?: boolean;
}) {
  const content = (
    <>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-elevated text-primary"><Icon className="h-4 w-4" /></span>
      <span className="min-w-0">
        <span className="block text-xs text-muted-foreground">{label}</span>
        <span className="block truncate text-sm font-medium text-foreground">{value || "No disponible"}</span>
      </span>
      {href && <ExternalLink className="ml-auto h-3.5 w-3.5 text-muted-foreground" />}
    </>
  );
  return href ? (
    <a href={href} target={external ? "_blank" : undefined} rel={external ? "noreferrer" : undefined} className="flex items-center gap-3 rounded-xl border border-border p-3 hover:bg-interactive/45">
      {content}
    </a>
  ) : (
    <div className="flex items-center gap-3 rounded-xl border border-border p-3">{content}</div>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-foreground">{value || "Sin atribución"}</dd>
    </div>
  );
}

function PermissionNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 rounded-xl border border-info/20 bg-info/8 p-4 text-sm leading-6 text-muted-foreground">
      <Info className="mt-1 h-4 w-4 shrink-0 text-info" />
      <p>{children}</p>
    </div>
  );
}
