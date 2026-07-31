"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  Check,
  CheckCircle2,
  FileImage,
  Loader2,
  Save,
  Send,
  Sparkles,
  Upload,
} from "lucide-react";
import type {
  Asset,
  AssetVariant,
  Brand,
  Platform,
  PublicationType,
  PublishingConnection,
  ThumbnailContentStyle,
  ThumbnailFormat,
} from "@rqt21/contracts";
import { PLATFORMS, PUBLICATION_TYPES } from "@rqt21/contracts";
import { PageHeader } from "@/components/design-system/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canAdmin, canWriteGrowth } from "@/lib/ui";
import { cn } from "@/lib/utils";
import { CONTENT_ANGLES, type ContentAngle } from "@/lib/content-angles";

const MAX_CAPTION_CTA_WORDS = 200;
const MAX_HASHTAGS = 5;

const STEPS = [
  { id: 1, label: "Destino", description: "Dónde se publicará" },
  { id: 2, label: "Contenido", description: "Foto, video y portada" },
  { id: 3, label: "Texto", description: "Caption, CTA y hashtags" },
  { id: 4, label: "Vista previa", description: "Revisión final" },
  { id: 5, label: "Publicar", description: "Ahora, después o borrador" },
] as const;

type WizardStep = (typeof STEPS)[number]["id"];
type PublishAction = "DRAFT" | "NOW" | "SCHEDULE";

const THUMBNAIL_CONTENT_STYLES: { value: ThumbnailContentStyle; label: string }[] = [
  { value: "receta", label: "Receta" },
  { value: "curiosidad", label: "Curiosidad" },
  { value: "encuesta", label: "Encuesta" },
  { value: "antes_despues", label: "Antes / Después" },
  { value: "receta_rapida", label: "Receta rápida" },
  { value: "educativo", label: "Educativo" },
];

const PLATFORM_LABELS: Partial<Record<Platform, string>> = {
  INSTAGRAM: "Instagram",
  FACEBOOK: "Facebook",
  YOUTUBE: "YouTube",
  TIKTOK: "TikTok",
  WHATSAPP: "WhatsApp",
  EMAIL: "Email",
  WEB: "Web",
  META_ADS: "Meta Ads",
  OTHER: "Otro",
};

const PUBLICATION_TYPE_LABELS: Partial<Record<PublicationType, string>> = {
  POST: "Publicación",
  REEL: "Reel",
  STORY: "Historia",
  CAROUSEL: "Carrusel",
  VIDEO: "Video",
  ARTICLE: "Artículo",
  EMAIL: "Email",
  OTHER: "Otro",
};

function detectAssetType(file: File): "VIDEO" | "IMAGE" {
  return file.type.startsWith("image/") ? "IMAGE" : "VIDEO";
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function parseHashtags(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => (token.startsWith("#") ? token : `#${token}`));
}

function friendlyError(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.detail : fallback;
}

function toLocalDateTimeValue(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 19);
}

export default function UploadReelPage() {
  const router = useRouter();
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((organization) => organization.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);
  const canPublishNow = canAdmin(org?.role);

  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [pubType, setPubType] = useState<PublicationType>("REEL");

  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [asset, setAsset] = useState<Asset | null>(null);

  const [aiTopic, setAiTopic] = useState("");
  const [aiAngle, setAiAngle] = useState<ContentAngle | "">("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const [thumbTitle, setThumbTitle] = useState("");
  const [thumbSubtitle, setThumbSubtitle] = useState("");
  const [thumbBenefits, setThumbBenefits] = useState(["", "", ""]);
  const [thumbCta, setThumbCta] = useState("");
  const [thumbStyle, setThumbStyle] = useState<ThumbnailContentStyle | "">("");
  const [thumbFormat, setThumbFormat] = useState<ThumbnailFormat>("vertical");
  const [thumbBusy, setThumbBusy] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);
  const [thumbnail, setThumbnail] = useState<AssetVariant | null>(null);

  const [contentTitle, setContentTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [cta, setCta] = useState("");
  const [hashtagsRaw, setHashtagsRaw] = useState("");

  const [publishAction, setPublishAction] = useState<PublishAction>("DRAFT");
  const [scheduledFor, setScheduledFor] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    url: string;
    action: PublishAction;
  } | null>(null);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [loadedBrands, loadedConnections] = await Promise.all([
        api.listBrands(currentOrgId),
        api.listConnections(currentOrgId).catch(() => []),
      ]);
      setBrands(loadedBrands);
      setConnections(loadedConnections);
      setBrandId((current) => current || loadedBrands[0]?.id || "");
      setConnectionId((current) => current || loadedConnections[0]?.id || "");
    } catch (loadError) {
      setError(friendlyError(loadError, "No pudimos cargar los datos para publicar."));
    } finally {
      setLoading(false);
    }
  }, [currentOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedBrand = brands.find((brand) => brand.id === brandId);
  const selectedConnection = connections.find((connection) => connection.id === connectionId);
  const hashtags = parseHashtags(hashtagsRaw);
  const wordCount = `${caption} ${cta}`.trim().split(/\s+/).filter(Boolean).length;
  const overWordLimit = wordCount > MAX_CAPTION_CTA_WORDS;
  const overHashtagLimit = hashtags.length > MAX_HASHTAGS;
  const automaticPublishingAvailable =
    canPublishNow && selectedConnection?.provider !== "MANUAL";

  const canContinue = (step: WizardStep) => {
    if (step === 1) return Boolean(brandId && connectionId && platform && pubType);
    // Require an asset only for platforms/types that need one (Instagram,
    // reels/videos). The backend enforces platform rules centrally; here
    // we allow the UI to skip upload when the chosen platform/type permit it
    // so the IA can generate text-only publications.
    if (step === 2) {
      const assetRequired = platform === "INSTAGRAM" || pubType === "REEL" || pubType === "VIDEO";
      return assetRequired ? Boolean(asset) : true;
    }
    if (step === 3) {
      return Boolean(contentTitle.trim() && !overWordLimit && !overHashtagLimit);
    }
    if (step === 5 && publishAction === "SCHEDULE") return Boolean(scheduledFor);
    return true;
  };

  const goNext = () => {
    if (!canContinue(currentStep) || currentStep === 5) return;
    setCurrentStep((currentStep + 1) as WizardStep);
  };

  const goBack = () => {
    if (currentStep === 1) return;
    setCurrentStep((currentStep - 1) as WizardStep);
  };

  const onUploadAsset = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !file || !brandId) return;
    setUploading(true);
    setUploadError(null);
    try {
      const upload = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "video/mp4",
        size_bytes: file.size,
        asset_type: detectAssetType(file),
        brand_id: brandId,
      });
      const contentBase64 = await fileToBase64(file);
      const uploadedAsset = await api.completeUpload(currentOrgId, {
        asset_id: upload.asset_id,
        content_base64: contentBase64,
      });
      setAsset(uploadedAsset);
      if (!contentTitle.trim()) {
        setContentTitle(file.name.replace(/\.[^/.]+$/, "").replaceAll(/[-_]+/g, " "));
      }
    } catch (uploadFailure) {
      setUploadError(friendlyError(uploadFailure, "No pudimos subir el archivo."));
    } finally {
      setUploading(false);
    }
  };

  const onGenerateCopy = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !brandId || !aiTopic.trim()) return;
    setAiBusy(true);
    setAiError(null);
    try {
      const angleInstruction = CONTENT_ANGLES.find((angle) => angle.value === aiAngle)?.instruction;
      // Angle goes into `objective` (read first, as the post's real goal),
      // not `notes` (read last, as a minor aside) — see content-angles.ts.
      const combinedObjective = [angleInstruction, "engagement"].filter(Boolean).join(" ").slice(0, 500);
      const job = await api.createGenerationJob(currentOrgId, {
        brand_id: brandId,
        generation_type: "SOCIAL_POST",
        input: {
          objective: combinedObjective,
          platform,
          topic: aiTopic,
        },
      });
      if (job.status === "FAILED") {
        setAiError(
          job.error_message
            ? `La IA no pudo generar el texto: ${job.error_message}`
            : "La IA no pudo generar el texto. Inténtalo nuevamente."
        );
        return;
      }
      if (job.status !== "COMPLETED" || !job.output_payload) {
        router.push(`/generation-jobs/${job.id}`);
        return;
      }
      const output = job.output_payload as {
        title?: string;
        caption?: string;
        cta?: string;
        hashtags?: string[];
      };
      if (output.title) setContentTitle(output.title);
      if (output.caption) setCaption(output.caption);
      if (output.cta) setCta(output.cta);
      if (output.hashtags?.length) setHashtagsRaw(output.hashtags.join(" "));
    } catch (generationError) {
      if (generationError instanceof ApiError && generationError.status === 402) {
        setAiError(`Límite de generación alcanzado: ${generationError.detail}`);
      } else {
        setAiError(friendlyError(generationError, "No pudimos generar el texto."));
      }
    } finally {
      setAiBusy(false);
    }
  };

  const onGenerateThumbnail = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentOrgId || !asset) return;
    setThumbBusy(true);
    setThumbError(null);
    try {
      const variant = await api.generateThumbnail(currentOrgId, asset.id, {
        title: thumbTitle,
        subtitle: thumbSubtitle || null,
        benefits: thumbBenefits.map((benefit) => benefit.trim()).filter(Boolean),
        cta_banner: thumbCta || null,
        content_style: thumbStyle || null,
        format: thumbFormat,
      });
      setThumbnail(variant);
    } catch (thumbnailError) {
      setThumbError(friendlyError(thumbnailError, "No pudimos generar la portada."));
    } finally {
      setThumbBusy(false);
    }
  };

  const onFinish = async (event: FormEvent) => {
    event.preventDefault();
    if (
      !currentOrgId ||
      !brandId ||
      !connectionId ||
      !contentTitle.trim() ||
      !canContinue(5)
    ) {
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const content = await api.createContent(currentOrgId, {
        brand_id: brandId,
        title: contentTitle.trim(),
        // If there's an asset, derive content_type from it; otherwise
        // derive from the selected publication type so AI-only posts
        // create the correct content item.
        content_type: asset
          ? asset.asset_type === "IMAGE"
            ? "POST"
            : "REEL"
          : pubType === "REEL"
          ? "REEL"
          : "POST",
        platform,
      });

      // This wizard's whole promise is "publica directo, sin pasar por el
      // consejo de revisión — la decides tú aquí mismo": choosing "Publicar
      // ahora" or "Programar" IS that decision, so it has to satisfy the
      // same content-approval check /validate enforces for every other
      // path, or it fails with a confusing "content is not APPROVED" error
      // right after the user already committed to publishing. Only
      // reachable when automaticPublishingAvailable gated the option to
      // OWNER/ADMIN in the first place (see canPublishNow below), matching
      // who's allowed to call this endpoint.
      if (publishAction !== "DRAFT") {
        await api.approveContent(currentOrgId, content.id, {
          comment: "Aprobado automáticamente al publicar desde Nueva publicación",
        });
      }

      const publicationPayload: any = {
        content_item_id: content.id,
        brand_id: brandId,
        publishing_connection_id: connectionId,
        platform,
        publication_type: pubType,
        title: contentTitle.trim(),
        caption,
        cta: cta || null,
        hashtags,
      };
      if (asset) {
        publicationPayload.asset_id = asset.id;
        publicationPayload.asset_variant_id = thumbnail?.id ?? null;
      }

      const publication = await api.createPublication(currentOrgId, publicationPayload);

      if (publishAction !== "DRAFT") {
        const validation = await api.validatePublication(currentOrgId, publication.id);
        if (!validation.ok) {
          setResult({ url: `/publishing/${publication.id}`, action: "DRAFT" });
          setFormError(
            `El borrador se guardó, pero necesita correcciones: ${validation.errors.join(" ")}`,
          );
          return;
        }
      }

      if (publishAction === "NOW") {
        await api.publishPublication(currentOrgId, publication.id);
      }

      if (publishAction === "SCHEDULE") {
        await api.schedulePublication(currentOrgId, publication.id, {
          scheduled_for: new Date(scheduledFor).toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        });
      }

      setResult({ url: `/publishing/${publication.id}`, action: publishAction });
    } catch (publishError) {
      setFormError(friendlyError(publishError, "No pudimos completar la publicación."));
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) {
    return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  }

  if (!canWrite) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          No tienes permisos para crear publicaciones. Solicita acceso a un administrador.
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 size-4 animate-spin" />
        Preparando el asistente…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Contenido"
        title="Nueva publicación"
        description="Prepara el contenido y decide al final si quieres publicarlo ahora, programarlo o guardarlo como borrador."
        actions={
          <Button asChild variant="outline">
            <Link href="/publishing">
              <ArrowLeft />
              Volver a publicaciones
            </Link>
          </Button>
        }
      />

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <nav aria-label="Progreso de la publicación" className="overflow-x-auto pb-1">
        <ol className="grid min-w-[720px] grid-cols-5 gap-2">
          {STEPS.map((step) => {
            const isActive = currentStep === step.id;
            const isComplete = currentStep > step.id;
            return (
              <li key={step.id}>
                <button
                  type="button"
                  onClick={() => {
                    if (step.id < currentStep || canContinue(currentStep)) {
                      setCurrentStep(step.id);
                    }
                  }}
                  aria-current={isActive ? "step" : undefined}
                  className={cn(
                    "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                    isActive && "border-primary/50 bg-primary/10",
                    isComplete && "border-success/30 bg-success/5",
                    !isActive && !isComplete && "border-border bg-card hover:bg-accent/50",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={cn(
                        "flex size-6 items-center justify-center rounded-full border text-xs font-semibold",
                        isActive && "border-primary bg-primary text-primary-foreground",
                        isComplete && "border-success bg-success text-success-foreground",
                      )}
                    >
                      {isComplete ? <Check className="size-3.5" /> : step.id}
                    </span>
                    <span className="text-sm font-medium text-foreground">{step.label}</span>
                  </span>
                  <span className="mt-1 block pl-8 text-xs text-muted-foreground">
                    {step.description}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <main>
          {currentStep === 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg text-foreground">¿Dónde quieres publicar?</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Elige la marca, la cuenta conectada y el formato de salida.
                </p>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <Field label="Marca" required>
                  <Select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
                    <option value="">Selecciona una marca</option>
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>
                        {brand.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Cuenta conectada" required>
                  <Select
                    value={connectionId}
                    onChange={(event) => setConnectionId(event.target.value)}
                  >
                    <option value="">Selecciona una conexión</option>
                    {connections.map((connection) => (
                      <option key={connection.id} value={connection.id}>
                        {connection.account_name} · {connection.provider}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Plataforma" required>
                  <Select
                    value={platform}
                    onChange={(event) => setPlatform(event.target.value as Platform)}
                  >
                    {PLATFORMS.map((item) => (
                      <option key={item} value={item}>
                        {PLATFORM_LABELS[item] ?? item}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Formato" required>
                  <Select
                    value={pubType}
                    onChange={(event) => setPubType(event.target.value as PublicationType)}
                  >
                    {PUBLICATION_TYPES.map((item) => (
                      <option key={item} value={item}>
                        {PUBLICATION_TYPE_LABELS[item] ?? item}
                      </option>
                    ))}
                  </Select>
                </Field>

                {connections.length === 0 && (
                  <div className="sm:col-span-2 rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm">
                    <p className="font-medium text-foreground">Primero conecta una cuenta</p>
                    <p className="mt-1 text-muted-foreground">
                      La conexión define dónde se enviará el contenido.
                    </p>
                    <Button asChild variant="outline" className="mt-3">
                      <Link href="/publishing/connections">Gestionar conexiones</Link>
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {currentStep === 2 && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg text-foreground">Añade una foto o video</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Este será el recurso principal de la publicación.
                  </p>
                </CardHeader>
                <CardContent>
                  {asset ? (
                    <div className="flex flex-col gap-4 rounded-xl border border-success/30 bg-success/5 p-4 sm:flex-row sm:items-center">
                      <div className="flex size-11 items-center justify-center rounded-lg bg-success/10 text-success">
                        <CheckCircle2 />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-foreground">
                          {asset.original_filename}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Archivo cargado correctamente · {asset.asset_type === "IMAGE" ? "Imagen" : "Video"}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setAsset(null);
                          setThumbnail(null);
                          setFile(null);
                        }}
                      >
                        Cambiar archivo
                      </Button>
                    </div>
                  ) : (
                    <form onSubmit={onUploadAsset} className="space-y-4">
                      <label className="flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 p-6 text-center transition-colors hover:border-primary/40 hover:bg-primary/5">
                        <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                          <Upload />
                        </span>
                        <span className="mt-4 font-medium text-foreground">
                          {file ? file.name : "Selecciona una foto o video"}
                        </span>
                        <span className="mt-1 text-sm text-muted-foreground">
                          Haz clic para buscar el archivo en tu equipo
                        </span>
                        <input
                          type="file"
                          accept="video/*,image/*"
                          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                          className="sr-only"
                        />
                      </label>
                      {uploadError && <InlineError message={uploadError} />}
                      <Button type="submit" disabled={uploading || !file || !brandId}>
                        {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
                        {uploading ? "Subiendo archivo…" : "Subir archivo"}
                      </Button>
                    </form>
                  )}
                </CardContent>
              </Card>

              {asset?.asset_type === "VIDEO" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base text-foreground">
                      Portada del video <Badge variant="secondary">Opcional</Badge>
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      Genera una portada con IA o continúa con el video original.
                    </p>
                  </CardHeader>
                  <CardContent>
                    {thumbnail ? (
                      <div className="flex items-center gap-3 rounded-lg border border-success/30 bg-success/5 p-4">
                        <CheckCircle2 className="text-success" />
                        <div className="flex-1 text-sm">
                          <p className="font-medium text-foreground">Portada generada</p>
                          <p className="text-muted-foreground">
                            {thumbnail.width} × {thumbnail.height}
                          </p>
                        </div>
                        <Button type="button" variant="outline" onClick={() => setThumbnail(null)}>
                          Generar otra
                        </Button>
                      </div>
                    ) : (
                      <form onSubmit={onGenerateThumbnail} className="space-y-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                          <Field label="Título de portada" required>
                            <Input
                              value={thumbTitle}
                              onChange={(event) => setThumbTitle(event.target.value)}
                              maxLength={200}
                            />
                          </Field>
                          <Field label="Subtítulo">
                            <Input
                              value={thumbSubtitle}
                              onChange={(event) => setThumbSubtitle(event.target.value)}
                              maxLength={200}
                            />
                          </Field>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-3">
                          {thumbBenefits.map((benefit, index) => (
                            <Field key={index} label={`Beneficio ${index + 1}`}>
                              <Input
                                value={benefit}
                                onChange={(event) =>
                                  setThumbBenefits((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? event.target.value : item,
                                    ),
                                  )
                                }
                                maxLength={80}
                              />
                            </Field>
                          ))}
                        </div>
                        <div className="grid gap-4 sm:grid-cols-3">
                          <Field label="Llamado a la acción">
                            <Input
                              value={thumbCta}
                              onChange={(event) => setThumbCta(event.target.value)}
                              maxLength={200}
                            />
                          </Field>
                          <Field label="Estilo">
                            <Select
                              value={thumbStyle}
                              onChange={(event) =>
                                setThumbStyle(event.target.value as ThumbnailContentStyle | "")
                              }
                            >
                              <option value="">Sin estilo específico</option>
                              {THUMBNAIL_CONTENT_STYLES.map((style) => (
                                <option key={style.value} value={style.value}>
                                  {style.label}
                                </option>
                              ))}
                            </Select>
                          </Field>
                          <Field label="Formato">
                            <Select
                              value={thumbFormat}
                              onChange={(event) =>
                                setThumbFormat(event.target.value as ThumbnailFormat)
                              }
                            >
                              <option value="vertical">Vertical</option>
                              <option value="facebook_horizontal">Horizontal</option>
                            </Select>
                          </Field>
                        </div>
                        {thumbError && <InlineError message={thumbError} />}
                        <Button type="submit" variant="outline" disabled={thumbBusy || !thumbTitle.trim()}>
                          {thumbBusy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                          {thumbBusy ? "Generando portada…" : "Generar portada con IA"}
                        </Button>
                      </form>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-4">
              <Card className="border-primary/20 bg-primary/[0.03]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-foreground">
                    <Sparkles className="text-primary" />
                    Escribir con IA
                    <Badge variant="secondary">Opcional</Badge>
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Describe el tema y la IA preparará un texto que podrás editar.
                  </p>
                </CardHeader>
                <CardContent>
                  <form onSubmit={onGenerateCopy} className="space-y-4">
                    <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
                      {CONTENT_ANGLES.map((angle) => (
                        <button
                          key={angle.value}
                          type="button"
                          onClick={() =>
                            setAiAngle((current) => (current === angle.value ? "" : angle.value))
                          }
                          aria-pressed={aiAngle === angle.value}
                          className={cn(
                            "rounded-lg border p-3 text-left text-xs transition-colors",
                            aiAngle === angle.value
                              ? "border-primary/50 bg-primary/10"
                              : "border-border bg-card hover:border-primary/30",
                          )}
                        >
                          <span className="block font-medium text-foreground">{angle.label}</span>
                          <span className="mt-1 block text-muted-foreground">{angle.hint}</span>
                        </button>
                      ))}
                    </div>
                    <Field label="¿De qué trata la publicación?">
                      <Input
                        value={aiTopic}
                        onChange={(event) => setAiTopic(event.target.value)}
                        placeholder="Ej.: 5 formas de mejorar tus campañas este mes"
                        maxLength={1000}
                      />
                    </Field>
                    {aiError && <InlineError message={aiError} />}
                    <Button type="submit" variant="outline" disabled={aiBusy || !aiTopic.trim()}>
                      {aiBusy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                      {aiBusy ? "Escribiendo…" : "Generar texto con IA"}
                    </Button>
                  </form>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg text-foreground">Texto de la publicación</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Revisa y edita el contenido antes de ver la vista previa.
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Field label="Título interno" required hint="Solo lo verá tu equipo.">
                    <Input
                      value={contentTitle}
                      onChange={(event) => setContentTitle(event.target.value)}
                      placeholder="Nombre para identificar esta publicación"
                    />
                  </Field>
                  <Field label="Caption">
                    <Textarea
                      value={caption}
                      onChange={(event) => setCaption(event.target.value)}
                      rows={7}
                      placeholder="Escribe el texto que acompañará la publicación…"
                    />
                  </Field>
                  <Field label="Llamado a la acción">
                    <Input
                      value={cta}
                      onChange={(event) => setCta(event.target.value)}
                      placeholder="Ej.: Conoce más en el enlace"
                    />
                  </Field>
                  <Field label="Hashtags" hint="Máximo 5, separados por espacio o coma.">
                    <Input
                      value={hashtagsRaw}
                      onChange={(event) => setHashtagsRaw(event.target.value)}
                      placeholder="#marketing #crecimiento"
                    />
                  </Field>
                  {hashtags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {hashtags.map((hashtag) => (
                        <Badge key={hashtag} variant="outline">
                          {hashtag}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-4 text-xs">
                    <span className={overWordLimit ? "text-destructive" : "text-muted-foreground"}>
                      Caption + CTA: {wordCount}/{MAX_CAPTION_CTA_WORDS} palabras
                    </span>
                    <span className={overHashtagLimit ? "text-destructive" : "text-muted-foreground"}>
                      Hashtags: {hashtags.length}/{MAX_HASHTAGS}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {currentStep === 4 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg text-foreground">Así se verá el contenido</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Comprueba el archivo y el texto antes de decidir cuándo publicarlo.
                </p>
              </CardHeader>
              <CardContent>
                <div className="mx-auto max-w-lg overflow-hidden rounded-2xl border border-border bg-background shadow-premium-lg">
                  <div className="flex items-center gap-3 border-b border-border p-4">
                    <div className="flex size-9 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                      {selectedBrand?.name.slice(0, 1).toUpperCase() ?? "R"}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {selectedBrand?.name ?? "Marca"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {PLATFORM_LABELS[platform] ?? platform}
                      </p>
                    </div>
                    <Badge variant="outline" className="ml-auto">
                      {PUBLICATION_TYPE_LABELS[pubType] ?? pubType}
                    </Badge>
                  </div>
                  <MediaPreview file={file} url={previewUrl} />
                  <div className="space-y-3 p-4">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                      {caption || "La publicación no tiene caption."}
                    </p>
                    {cta && <p className="text-sm font-medium text-foreground">{cta}</p>}
                    {hashtags.length > 0 && (
                      <p className="text-sm text-primary">{hashtags.join(" ")}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {currentStep === 5 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg text-foreground">¿Qué quieres hacer ahora?</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Ya no necesitas validar en otra pantalla: el asistente hará ese paso automáticamente.
                </p>
              </CardHeader>
              <CardContent>
                {result ? (
                  <SuccessState action={result.action} url={result.url} />
                ) : (
                  <form onSubmit={onFinish} className="space-y-5">
                    <div className="grid gap-3">
                      <ActionOption
                        active={publishAction === "NOW"}
                        disabled={!automaticPublishingAvailable}
                        icon={<Send />}
                        title="Publicar ahora"
                        description={
                          automaticPublishingAvailable
                            ? "Valida y envía el contenido a la cuenta conectada."
                            : selectedConnection?.provider === "MANUAL"
                              ? "Esta conexión es manual. Elige borrador para publicarlo fuera de RQT21."
                              : "Solo un administrador u Owner puede autorizar la publicación automática."
                        }
                        onClick={() => setPublishAction("NOW")}
                      />
                      <ActionOption
                        active={publishAction === "SCHEDULE"}
                        disabled={!canPublishNow}
                        icon={<CalendarClock />}
                        title="Programar"
                        description={
                          canPublishNow
                            ? "Valida ahora y publica automáticamente en la fecha elegida."
                            : "Solo un administrador u Owner puede autorizar que esto salga en vivo, aunque sea programado."
                        }
                        onClick={() => setPublishAction("SCHEDULE")}
                      />
                      <ActionOption
                        active={publishAction === "DRAFT"}
                        icon={<Save />}
                        title="Guardar como borrador"
                        description="Conserva el contenido para revisarlo o publicarlo más adelante."
                        onClick={() => setPublishAction("DRAFT")}
                      />
                    </div>

                    {publishAction === "SCHEDULE" && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                        <Field
                          label="Fecha y hora de publicación"
                          required
                          hint={`Se usará tu zona horaria: ${Intl.DateTimeFormat().resolvedOptions().timeZone}.`}
                        >
                          <Input
                            type="datetime-local"
                            step={1}
                            value={scheduledFor}
                            min={toLocalDateTimeValue(new Date())}
                            onChange={(event) => setScheduledFor(event.target.value)}
                          />
                        </Field>
                      </div>
                    )}

                    {formError && <InlineError message={formError} />}

                    <Button
                      type="submit"
                      size="lg"
                      disabled={
                        submitting ||
                        (publishAction === "NOW" && !automaticPublishingAvailable) ||
                        (publishAction === "SCHEDULE" && !canPublishNow) ||
                        !canContinue(5)
                      }
                    >
                      {submitting ? (
                        <Loader2 className="animate-spin" />
                      ) : publishAction === "NOW" ? (
                        <Send />
                      ) : publishAction === "SCHEDULE" ? (
                        <CalendarClock />
                      ) : (
                        <Save />
                      )}
                      {submitting
                        ? "Procesando…"
                        : publishAction === "NOW"
                          ? "Publicar ahora"
                          : publishAction === "SCHEDULE"
                            ? "Programar publicación"
                            : "Guardar borrador"}
                    </Button>
                  </form>
                )}
              </CardContent>
            </Card>
          )}

          {!result && (
            <div className="mt-5 flex items-center justify-between">
              <Button type="button" variant="outline" onClick={goBack} disabled={currentStep === 1}>
                <ArrowLeft />
                Anterior
              </Button>
              {currentStep < 5 && (
                <Button type="button" onClick={goNext} disabled={!canContinue(currentStep)}>
                  Continuar
                  <ArrowRight />
                </Button>
              )}
            </div>
          )}
        </main>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">Resumen</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <SummaryItem label="Marca" value={selectedBrand?.name || "Sin seleccionar"} />
              <SummaryItem
                label="Destino"
                value={
                  selectedConnection
                    ? `${selectedConnection.account_name} · ${selectedConnection.provider}`
                    : "Sin seleccionar"
                }
              />
              <SummaryItem
                label="Formato"
                value={`${PLATFORM_LABELS[platform] ?? platform} · ${
                  PUBLICATION_TYPE_LABELS[pubType] ?? pubType
                }`}
              />
              <SummaryItem
                label="Archivo"
                value={asset?.original_filename || "Pendiente"}
                complete={Boolean(asset)}
              />
              <SummaryItem
                label="Texto"
                value={contentTitle.trim() ? "Preparado" : "Pendiente"}
                complete={Boolean(contentTitle.trim())}
              />
              <div className="border-t border-border pt-4">
                <p className="text-xs leading-5 text-muted-foreground">
                  Esta vía publica directo, sin pasar por el consejo de revisión — la decides tú
                  aquí mismo. Si prefieres que la IA{" "}
                  <Link href="/generate" className="font-medium text-primary hover:underline">
                    genere el contenido
                  </Link>{" "}
                  y lo evalúe automáticamente, revisa el resultado en{" "}
                  <Link href="/reviews" className="font-medium text-primary hover:underline">
                    Revisiones
                  </Link>
                  .
                </p>
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-foreground">
        {label}
        {required && <span className="ml-1 text-primary">*</span>}
      </span>
      <span className="mt-1 block">{children}</span>
      {hint && <span className="mt-1.5 block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      {message}
    </div>
  );
}

function SummaryItem({
  label,
  value,
  complete,
}: {
  label: string;
  value: string;
  complete?: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        className={cn(
          "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
          complete ? "border-success/40 bg-success/10 text-success" : "border-border text-muted-foreground",
        )}
      >
        {complete ? <Check className="size-3" /> : <span className="size-1 rounded-full bg-current" />}
      </span>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="truncate font-medium text-foreground">{value}</p>
      </div>
    </div>
  );
}

function MediaPreview({ file, url }: { file: File | null; url: string | null }) {
  if (!file || !url) {
    return (
      <div className="flex aspect-square items-center justify-center bg-muted/30 text-muted-foreground">
        <FileImage className="size-10" />
      </div>
    );
  }

  if (file.type.startsWith("image/")) {
    // The local object URL is only used for an immediate, private preview.
    return (
      <Image
        src={url}
        alt="Vista previa del recurso"
        width={1080}
        height={1080}
        unoptimized
        className="max-h-[560px] w-full object-cover"
      />
    );
  }

  return (
    <video controls className="max-h-[560px] w-full bg-black">
      <source src={url} type={file.type} />
    </video>
  );
}

function ActionOption({
  active,
  disabled,
  icon,
  title,
  description,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "flex min-h-20 w-full items-start gap-4 rounded-xl border p-4 text-left transition-colors",
        active ? "border-primary/50 bg-primary/10" : "border-border bg-card hover:border-primary/30",
        disabled && "cursor-not-allowed opacity-55",
      )}
    >
      <span
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-lg",
          active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
      >
        {icon}
      </span>
      <span>
        <span className="block font-medium text-foreground">{title}</span>
        <span className="mt-1 block text-sm leading-5 text-muted-foreground">{description}</span>
      </span>
      <span
        aria-hidden="true"
        className={cn(
          "ml-auto mt-1 flex size-5 shrink-0 items-center justify-center rounded-full border",
          active && "border-primary bg-primary text-primary-foreground",
        )}
      >
        {active && <Check className="size-3" />}
      </span>
    </button>
  );
}

function SuccessState({ action, url }: { action: PublishAction; url: string }) {
  const copy =
    action === "NOW"
      ? {
          title: "Publicación enviada",
          description: "El contenido fue validado y enviado a la cuenta conectada.",
        }
      : action === "SCHEDULE"
        ? {
            title: "Publicación programada",
            description: "El contenido quedó validado y se publicará en la fecha seleccionada.",
          }
        : {
            title: "Borrador guardado",
            description: "Puedes volver más tarde para validar, programar o publicar el contenido.",
          };

  return (
    <div className="flex flex-col items-center py-8 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-success/10 text-success">
        <CheckCircle2 className="size-7" />
      </span>
      <h2 className="mt-4 text-xl font-semibold text-foreground">{copy.title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">{copy.description}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button asChild>
          <Link href={url}>Ver publicación</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/publishing">Ir a publicaciones</Link>
        </Button>
      </div>
    </div>
  );
}
