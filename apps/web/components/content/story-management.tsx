"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarClock,
  Check,
  Camera,
  ClipboardList,
  ImageUp,
  MessageCircle,
  Play,
  Power,
  RefreshCw,
  Repeat,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type {
  Brand,
  ContentItem,
  StoryConfig,
  StoryPendingPhoto,
  Platform,
  PublishingConnection,
} from "@rqt21/contracts";

import { MetricCard } from "@/components/design-system/metric-card";
import { PageHeader } from "@/components/design-system/page-header";
import { SectionHeader } from "@/components/design-system/section-header";
import { StatusBadge, type StatusTone } from "@/components/design-system/status-badge";
import { LoadingSkeleton, StatePanel } from "@/components/design-system/state-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin } from "@/lib/ui";
import { cn } from "@/lib/utils";

const REVIEW_TONE: Record<string, StatusTone> = {
  NOT_SUBMITTED: "neutral",
  IN_REVIEW: "info",
  APPROVED: "success",
  CHANGES_REQUESTED: "warning",
  REJECTED: "danger",
};

const REVIEW_LABEL: Record<string, string> = {
  NOT_SUBMITTED: "Sin enviar",
  IN_REVIEW: "En revisión",
  APPROVED: "Aprobado",
  CHANGES_REQUESTED: "Cambios solicitados",
  REJECTED: "Rechazado",
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "Nunca";
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "numeric",
      month: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function StoryManagement() {
  const { currentOrgId, organizations } = useAuth();
  const organization = organizations.find((candidate) => candidate.id === currentOrgId);
  const canWrite = canAdmin(organization?.role);

  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState("");
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [config, setConfig] = useState<StoryConfig | null>(null);
  const [history, setHistory] = useState<ContentItem[]>([]);
  const [pendingPhotos, setPendingPhotos] = useState<StoryPendingPhoto[]>([]);
  const [uploadingId, setUploadingId] = useState<string | null>(null);

  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [enabled, setEnabled] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [intervalMinutes, setIntervalMinutes] = useState(40);
  const [maxPerDay, setMaxPerDay] = useState(12);

  const loadBrands = useCallback(async () => {
    if (!currentOrgId) return;
    setLoadingBrands(true);
    setError(null);
    try {
      const result = await api.listBrands(currentOrgId);
      setBrands(result);
      setBrandId((current) => current || result[0]?.id || "");
    } catch (loadError) {
      setError(
        loadError instanceof ApiError ? loadError.detail : "No pudimos cargar las marcas.",
      );
    } finally {
      setLoadingBrands(false);
    }
  }, [currentOrgId]);

  const loadForBrand = useCallback(async () => {
    if (!currentOrgId || !brandId) return;
    setLoadingConfig(true);
    setError(null);
    setSaved(false);
    try {
      const [connectionResult, configResult, historyResult, pendingResult] = await Promise.all([
        api.listConnections(currentOrgId),
        api.getStoryConfig(currentOrgId, brandId),
        api.listStoryHistory(currentOrgId, brandId),
        api.listStoryPendingPhotos(currentOrgId, brandId),
      ]);
      setConnections(connectionResult.filter((c) => c.brand_id === brandId));
      setConfig(configResult);
      setEnabled(configResult.enabled);
      setConnectionId(configResult.publishing_connection_id ?? "");
      setIntervalMinutes(configResult.interval_minutes);
      setMaxPerDay(configResult.max_per_day);
      setHistory(historyResult);
      setPendingPhotos(pendingResult);
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.detail
          : "No pudimos cargar la configuración de Historias.",
      );
    } finally {
      setLoadingConfig(false);
    }
  }, [brandId, currentOrgId]);

  useEffect(() => {
    void loadBrands();
  }, [loadBrands]);

  useEffect(() => {
    void loadForBrand();
  }, [loadForBrand]);

  const selectedConnection = useMemo(
    () => connections.find((c) => c.id === connectionId) ?? null,
    [connections, connectionId],
  );

  const save = async () => {
    if (!currentOrgId || !brandId) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updateStoryConfig(currentOrgId, brandId, {
        enabled,
        publishing_connection_id: connectionId || null,
        platform: (selectedConnection?.platform ?? "INSTAGRAM") as Platform,
        interval_minutes: intervalMinutes,
        max_per_day: maxPerDay,
      });
      setConfig(updated);
      setEnabled(updated.enabled);
      setSaved(true);
    } catch (saveError) {
      setError(
        saveError instanceof ApiError
          ? saveError.detail
          : "No pudimos guardar la configuración.",
      );
    } finally {
      setSaving(false);
    }
  };

  const runNow = async () => {
    if (!currentOrgId || !brandId) return;
    setRunning(true);
    setError(null);
    try {
      const updated = await api.runStoryNow(currentOrgId, brandId);
      setConfig(updated);
      const [historyResult, pendingResult] = await Promise.all([
        api.listStoryHistory(currentOrgId, brandId),
        api.listStoryPendingPhotos(currentOrgId, brandId),
      ]);
      setHistory(historyResult);
      setPendingPhotos(pendingResult);
    } catch (runError) {
      setError(
        runError instanceof ApiError
          ? runError.detail
          : "No pudimos generar las historias de hoy.",
      );
    } finally {
      setRunning(false);
    }
  };

  const uploadPhoto = async (item: StoryPendingPhoto, file: File) => {
    if (!currentOrgId || !brandId) return;
    const contentId = item.id;
    setUploadingId(contentId);
    setError(null);
    try {
      const init = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "image/jpeg",
        size_bytes: file.size,
        asset_type: "IMAGE",
        brand_id: brandId,
        content_item_id: contentId,
        // Facebook/Instagram both require alt text on the image before a
        // publish is allowed (validate_publication_draft) — the upload
        // widget has no separate field for it, so the story's own title
        // stands in, same as any accessible photo description.
        alt_text: item.title || null,
      });
      await api.completeUpload(currentOrgId, {
        asset_id: init.asset_id,
        content_base64: await fileToBase64(file),
      });
      const [pendingResult, historyResult, configResult] = await Promise.all([
        api.listStoryPendingPhotos(currentOrgId, brandId),
        api.listStoryHistory(currentOrgId, brandId),
        api.getStoryConfig(currentOrgId, brandId),
      ]);
      setPendingPhotos(pendingResult);
      setHistory(historyResult);
      setConfig(configResult);
    } catch (uploadError) {
      setError(
        uploadError instanceof ApiError
          ? uploadError.detail
          : "No pudimos subir la foto. Intenta de nuevo.",
      );
    } finally {
      setUploadingId(null);
    }
  };

  if (!currentOrgId) {
    return (
      <StatePanel
        icon={MessageCircle}
        title="Selecciona una organización"
        description="El ciclo de Historias aparecerá cuando elijas una organización."
      />
    );
  }

  const eligibleConnections = connections.filter((c) => c.status === "ACTIVE");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Contenido"
        title="Historias"
        description="Genera automáticamente historias cortas y conversacionales (preguntas, encuestas, detrás de cámaras) para conectar con tus seguidores, cada pocos minutos. La foto la subes tú para cada una — así garantizamos la calidad de la imagen — y se publica en su horario asignado en cuanto la subas."
        metadata={
          <>
            <StatusBadge
              label={config?.enabled ? "Ciclo activo" : "Ciclo desactivado"}
              tone={config?.enabled ? "success" : "neutral"}
            />
            {!canWrite && (
              <span className="text-xs text-muted-foreground">Solo lectura para tu rol</span>
            )}
          </>
        }
        actions={
          <Button variant="outline" size="sm" onClick={() => void loadForBrand()} disabled={loadingConfig}>
            <RefreshCw className={cn("h-4 w-4", loadingConfig && "animate-spin")} />
            Actualizar
          </Button>
        }
      />

      {error && <InlineError>{error}</InlineError>}
      {saved && (
        <div role="status" className="flex items-center gap-2 rounded-xl border border-success/25 bg-success/5 px-4 py-3 text-sm text-success">
          <Check className="h-4 w-4" />
          Configuración guardada.
        </div>
      )}

      {loadingBrands ? (
        <LoadingSkeleton rows={4} />
      ) : brands.length === 0 ? (
        <StatePanel
          icon={MessageCircle}
          title="Primero crea una marca"
          description="El ciclo de Historias se configura por marca."
          actionLabel="Ir a marcas"
          onAction={() => window.location.assign("/brands")}
        />
      ) : (
        <>
          <Card className="bg-card/80 shadow-none">
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-end sm:justify-between">
              <label className="block w-full max-w-md space-y-1.5 text-sm">
                <span className="font-medium text-foreground">Marca activa</span>
                <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
                  {brands.map((brand) => (
                    <option key={brand.id} value={brand.id}>{brand.name}</option>
                  ))}
                </Select>
              </label>
              {!canWrite && (
                <p className="flex max-w-md items-start gap-2 text-xs leading-5 text-muted-foreground">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                  Configurar Historias requiere rol OWNER o ADMIN.
                </p>
              )}
            </CardContent>
          </Card>

          {loadingConfig ? (
            <LoadingSkeleton rows={6} />
          ) : (
            <>
              <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5" aria-label="Resumen de Historias">
                <MetricCard
                  label="Publicaciones hoy"
                  value={`${config?.daily_count ?? 0} / ${maxPerDay}`}
                  helper="Se reinicia cada día"
                  icon={Repeat}
                  tone="info"
                />
                <MetricCard
                  label="Última generación"
                  value={
                    <span className="text-base font-semibold leading-snug">
                      {formatDateTime(config?.last_run_at ?? null)}
                    </span>
                  }
                  helper={`Horarios cada ${intervalMinutes} min`}
                  icon={CalendarClock}
                />
                <MetricCard
                  label="Cuenta de destino"
                  value={
                    <span className="block truncate text-lg font-semibold">
                      {selectedConnection?.account_name ?? "Sin conectar"}
                    </span>
                  }
                  helper={selectedConnection ? selectedConnection.platform : "No se publica nada sin conexión"}
                  icon={ShieldCheck}
                  tone={selectedConnection ? "positive" : "warning"}
                />
                <MetricCard
                  label="Esperando foto"
                  value={pendingPhotos.length}
                  helper={
                    selectedConnection
                      ? "Se publican solas al subir la foto"
                      : "Conecta una cuenta para publicar automáticamente"
                  }
                  icon={ImageUp}
                  tone={pendingPhotos.length > 0 ? "warning" : "positive"}
                />
                <MetricCard
                  label="Publicadas en Historias"
                  value={history.length}
                  helper="Historial reciente generado automáticamente"
                  icon={ClipboardList}
                />
              </section>

              <Card className="bg-card/80 shadow-none">
                <CardContent className="p-5 sm:p-6">
                  <SectionHeader
                    title={
                      <span className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        Configuración del ciclo
                      </span>
                    }
                    description="Genera de una vez todo el día de historias (hasta el máximo configurado), cada una con su horario asignado cada tantos minutos. Solo si el consejo de auto-aprobación lo aprueba pasa a 'Esperando foto' — tú subes la imagen y sale publicada en su horario (o al instante si ese horario ya pasó)."
                  />

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="flex items-center justify-between rounded-xl border border-border bg-interactive px-4 py-3 md:col-span-2">
                      <div>
                        <p className="text-sm font-medium text-foreground">Ciclo automático</p>
                        <p className="text-xs text-muted-foreground">
                          Desactivado no genera texto nuevo, aunque queden historias previas esperando foto.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant={enabled ? "default" : "outline"}
                        size="sm"
                        disabled={!canWrite}
                        onClick={() => setEnabled((v) => !v)}
                      >
                        <Power className="h-4 w-4" />
                        {enabled ? "Activado" : "Desactivado"}
                      </Button>
                    </div>

                    <label className="block space-y-1.5 text-sm">
                      <span className="font-medium text-foreground">Cuenta de publicación</span>
                      <Select
                        value={connectionId}
                        onChange={(event) => setConnectionId(event.target.value)}
                        disabled={!canWrite}
                      >
                        <option value="">Sin conectar (solo queda en Bandeja)</option>
                        {eligibleConnections.map((connection) => (
                          <option key={connection.id} value={connection.id}>
                            {connection.platform} · {connection.account_name}
                          </option>
                        ))}
                      </Select>
                      {eligibleConnections.length === 0 && (
                        <span className="block text-xs leading-5 text-muted-foreground">
                          No hay cuentas activas para esta marca — conecta una en{" "}
                          <a href="/publishing/connections" className="underline">Distribución</a>.
                        </span>
                      )}
                    </label>

                    <label className="block space-y-1.5 text-sm">
                      <span className="font-medium text-foreground">Intervalo (minutos)</span>
                      <Input
                        type="number"
                        min={10}
                        max={360}
                        value={intervalMinutes}
                        onChange={(event) => setIntervalMinutes(Number(event.target.value) || 10)}
                        disabled={!canWrite}
                      />
                    </label>

                    <label className="block space-y-1.5 text-sm">
                      <span className="font-medium text-foreground">Máximo por día</span>
                      <Input
                        type="number"
                        min={1}
                        max={36}
                        value={maxPerDay}
                        onChange={(event) => setMaxPerDay(Number(event.target.value) || 1)}
                        disabled={!canWrite}
                      />
                    </label>
                  </div>

                  {canWrite && (
                    <div className="mt-6 flex flex-wrap justify-end gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void runNow()}
                        disabled={running || !config?.enabled}
                        title={!config?.enabled ? "Activa y guarda el ciclo primero" : undefined}
                      >
                        <Play className="h-4 w-4" />
                        {running ? "Generando…" : "Generar historias de hoy"}
                      </Button>
                      <Button type="button" onClick={() => void save()} disabled={saving}>
                        {saving ? "Guardando…" : "Guardar"}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-card/80 shadow-none">
                <CardContent className="p-5 sm:p-6">
                  <SectionHeader
                    title={
                      <span className="flex items-center gap-2">
                        <Camera className="h-4 w-4 text-primary" />
                        Esperando foto
                      </span>
                    }
                    description="Textos ya aprobados por el consejo, cada uno con su horario asignado — sube la foto y sale publicada en ese horario (o al instante si ya pasó)."
                  />
                  {pendingPhotos.length === 0 ? (
                    <p className="mt-4 text-sm text-muted-foreground">
                      No hay historias esperando foto por ahora.
                    </p>
                  ) : (
                    <ul className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                      {pendingPhotos.map((item) => (
                        <PendingPhotoCard
                          key={item.id}
                          item={item}
                          uploading={uploadingId === item.id}
                          disabled={uploadingId !== null}
                          onUpload={(file) => void uploadPhoto(item, file)}
                        />
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-card/80 shadow-none">
                <CardContent className="p-5 sm:p-6">
                  <SectionHeader
                    title="Historias recientes"
                    description="Generadas automáticamente por este ciclo, con su estado de revisión."
                  />
                  {history.length === 0 ? (
                    <p className="mt-4 text-sm text-muted-foreground">
                      Todavía no se ha generado ninguna historia para esta marca.
                    </p>
                  ) : (
                    <ul className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                      {history.map((item) => (
                        <li key={item.id}>
                          <div className="flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-sm">
                            <div className="flex items-start justify-between gap-2">
                              <StatusBadge
                                label={REVIEW_LABEL[item.review_status] ?? item.review_status}
                                tone={REVIEW_TONE[item.review_status] ?? "neutral"}
                              />
                              <span className="shrink-0 text-xs text-muted-foreground">
                                {formatDateTime(item.created_at)}
                              </span>
                            </div>
                            <div className="min-w-0">
                              <p className="line-clamp-2 text-sm font-semibold text-foreground">{item.title}</p>
                              {item.caption && (
                                <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                                  {item.caption}
                                </p>
                              )}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}

function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}

function PendingPhotoCard({
  item,
  uploading,
  disabled,
  onUpload,
}: {
  item: StoryPendingPhoto;
  uploading: boolean;
  disabled: boolean;
  onUpload: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <li>
      <div className="flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-premium">
        <div className="flex items-start justify-between gap-2">
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600 dark:text-amber-400">
            <CalendarClock className="h-3.5 w-3.5" />
            {item.scheduled_for ? formatDateTime(item.scheduled_for) : "Instantáneo"}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm font-semibold text-foreground">{item.title}</p>
          {item.caption && (
            <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
              {item.caption}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 pt-1">
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            size="sm"
            className="w-full"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            <ImageUp className="h-4 w-4" />
            {uploading ? "Subiendo…" : "Subir foto"}
          </Button>
        </div>
      </div>
    </li>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1] ?? "";
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
