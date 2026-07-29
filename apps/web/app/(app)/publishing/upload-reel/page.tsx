"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

const MAX_CAPTION_CTA_WORDS = 200;
const MAX_HASHTAGS = 5;

function detectAssetType(file: File): "VIDEO" | "IMAGE" {
  return file.type.startsWith("image/") ? "IMAGE" : "VIDEO";
}

const THUMBNAIL_CONTENT_STYLES: { value: ThumbnailContentStyle; label: string }[] = [
  { value: "receta", label: "Receta" },
  { value: "curiosidad", label: "Curiosidad" },
  { value: "encuesta", label: "Encuesta" },
  { value: "antes_despues", label: "Antes / Después" },
  { value: "receta_rapida", label: "Receta rápida" },
  { value: "educativo", label: "Educativo" },
];

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
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => (t.startsWith("#") ? t : `#${t}`));
}

export default function UploadReelPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [brands, setBrands] = useState<Brand[]>([]);
  const [connections, setConnections] = useState<PublishingConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: destino
  const [brandId, setBrandId] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [platform, setPlatform] = useState<Platform>("INSTAGRAM");
  const [pubType, setPubType] = useState<PublicationType>("REEL");

  // Step 2: archivo (video o imagen)
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [asset, setAsset] = useState<Asset | null>(null);

  // Paso "Generar texto con IA" (caption + CTA + hashtags a partir de un título)
  const [aiTopic, setAiTopic] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Step 3: miniatura
  const [thumbTitle, setThumbTitle] = useState("");
  const [thumbSubtitle, setThumbSubtitle] = useState("");
  const [thumbBenefits, setThumbBenefits] = useState(["", "", ""]);
  const [thumbCta, setThumbCta] = useState("");
  const [thumbStyle, setThumbStyle] = useState<ThumbnailContentStyle | "">("");
  const [thumbFormat, setThumbFormat] = useState<ThumbnailFormat>("vertical");
  const [thumbBusy, setThumbBusy] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);
  const [thumbnail, setThumbnail] = useState<AssetVariant | null>(null);

  // Step 4: publicación
  const [contentTitle, setContentTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [cta, setCta] = useState("");
  const [hashtagsRaw, setHashtagsRaw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [bs, conns] = await Promise.all([
        api.listBrands(currentOrgId),
        api.listConnections(currentOrgId).catch(() => []),
      ]);
      setBrands(bs);
      setConnections(conns);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
      if (!connectionId && conns.length > 0) setConnectionId(conns[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId, connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onUploadVideo = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !file || !brandId) return;
    setUploading(true);
    setUploadError(null);
    try {
      const init = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "video/mp4",
        size_bytes: file.size,
        asset_type: detectAssetType(file),
        brand_id: brandId,
      });
      const content_base64 = await fileToBase64(file);
      const uploaded = await api.completeUpload(currentOrgId, {
        asset_id: init.asset_id,
        content_base64,
      });
      setAsset(uploaded);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.detail : "Error al subir el archivo");
    } finally {
      setUploading(false);
    }
  };

  const onGenerateCopy = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId || !aiTopic.trim()) return;
    setAiBusy(true);
    setAiError(null);
    try {
      const job = await api.createGenerationJob(currentOrgId, {
        brand_id: brandId,
        generation_type: "SOCIAL_POST",
        input: {
          objective: "engagement",
          platform,
          topic: aiTopic,
        },
      });
      if (job.status !== "COMPLETED" || !job.output_payload) {
        setAiError("La IA no pudo generar el texto — probá de nuevo.");
        return;
      }
      const out = job.output_payload as {
        title?: string;
        caption?: string;
        cta?: string;
        hashtags?: string[];
      };
      if (out.title && !contentTitle.trim()) setContentTitle(out.title);
      if (out.caption) setCaption(out.caption);
      if (out.cta) setCta(out.cta);
      if (Array.isArray(out.hashtags) && out.hashtags.length > 0) {
        setHashtagsRaw(out.hashtags.join(" "));
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setAiError(`Límite de generación alcanzado: ${err.detail}`);
      } else {
        setAiError(err instanceof ApiError ? err.detail : "Error generando el texto");
      }
    } finally {
      setAiBusy(false);
    }
  };

  const onGenerateThumbnail = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !asset) return;
    setThumbBusy(true);
    setThumbError(null);
    try {
      const variant = await api.generateThumbnail(currentOrgId, asset.id, {
        title: thumbTitle,
        subtitle: thumbSubtitle || null,
        benefits: thumbBenefits.map((b) => b.trim()).filter(Boolean),
        cta_banner: thumbCta || null,
        content_style: thumbStyle || null,
        format: thumbFormat,
      });
      setThumbnail(variant);
    } catch (err) {
      setThumbError(err instanceof ApiError ? err.detail : "Error al generar la miniatura");
    } finally {
      setThumbBusy(false);
    }
  };

  const hashtags = parseHashtags(hashtagsRaw);
  const wordCount = `${caption} ${cta}`.trim().split(/\s+/).filter(Boolean).length;
  const overWordLimit = wordCount > MAX_CAPTION_CTA_WORDS;
  const overHashtagLimit = hashtags.length > MAX_HASHTAGS;

  const onPublish = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !asset || !brandId || !connectionId || !contentTitle.trim()) return;
    if (overWordLimit || overHashtagLimit) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const content = await api.createContent(currentOrgId, {
        brand_id: brandId,
        title: contentTitle,
        content_type: asset.asset_type === "IMAGE" ? "POST" : "REEL",
        platform,
      });
      const publication = await api.createPublication(currentOrgId, {
        content_item_id: content.id,
        brand_id: brandId,
        publishing_connection_id: connectionId,
        asset_id: asset.id,
        asset_variant_id: thumbnail?.id ?? null,
        platform,
        publication_type: pubType,
        caption,
        cta: cta || null,
        hashtags,
      });
      setPublishedUrl(`/publishing/${publication.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error al crear la publicación");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Subir contenido manual</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Subí un video o una foto ya lista, generá su miniatura o su texto con IA,
            y preparalo como publicación — en un solo lugar.
          </p>
        </div>
        <Link href="/publishing" className="text-sm text-primary hover:underline">
          ← Publicaciones
        </Link>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {!canWrite ? (
        <p className="text-sm text-muted-foreground">No tenés permisos para crear publicaciones.</p>
      ) : loading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          {/* Paso 1: destino */}
          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-base">1. Destino</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Conexión</span>
                  <Select value={connectionId} onChange={(e) => setConnectionId(e.target.value)} className="mt-1">
                    <option value="">Sin conexión</option>
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.account_name} ({c.provider})</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Plataforma</span>
                  <Select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="mt-1">
                    {PLATFORMS.map((p) => (<option key={p} value={p}>{p}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Tipo de publicación</span>
                  <Select value={pubType} onChange={(e) => setPubType(e.target.value as PublicationType)} className="mt-1">
                    {PUBLICATION_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
                  </Select>
                </label>
              </div>
              {connections.length === 0 && (
                <p className="mt-3 text-xs text-warning">
                  No hay conexiones activas. Podés seguir y crear el borrador, pero hace falta{" "}
                  <Link href="/publishing/connections" className="text-primary hover:underline">
                    una conexión
                  </Link>{" "}
                  antes de publicar de verdad.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Paso 2: subir video o imagen */}
          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-base">2. Video o foto</CardTitle>
            </CardHeader>
            <CardContent>
              {asset ? (
                <div className="flex items-center gap-2 text-sm">
                  <Badge variant="success">Subido</Badge>
                  <span>{asset.original_filename}</span>
                  <Badge variant="outline">{asset.asset_type}</Badge>
                  <Button variant="outline" onClick={() => setAsset(null)} className="ml-auto">
                    Cambiar archivo
                  </Button>
                </div>
              ) : (
                <form onSubmit={onUploadVideo} className="space-y-3">
                  <input
                    type="file"
                    accept="video/*,image/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="w-full text-sm"
                  />
                  {uploadError && (
                    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {uploadError}
                    </div>
                  )}
                  <Button type="submit" disabled={uploading || !file || !brandId}>
                    {uploading ? "Subiendo…" : "Subir archivo"}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          {/* Paso 3: miniatura (solo videos) */}
          {asset && asset.asset_type === "VIDEO" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-foreground text-base">3. Miniatura (IA)</CardTitle>
              </CardHeader>
              <CardContent>
                {thumbnail ? (
                  <div className="flex items-center gap-2 text-sm">
                    <Badge variant="success">Generada</Badge>
                    <span>{thumbnail.width}x{thumbnail.height}</span>
                    <Button variant="outline" onClick={() => setThumbnail(null)} className="ml-auto">
                      Generar otra
                    </Button>
                  </div>
                ) : (
                  <form onSubmit={onGenerateThumbnail} className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="block text-sm">
                        <span className="text-muted-foreground">Título *</span>
                        <Input value={thumbTitle} onChange={(e) => setThumbTitle(e.target.value)} required maxLength={200} className="mt-1" />
                      </label>
                      <label className="block text-sm">
                        <span className="text-muted-foreground">Subtítulo</span>
                        <Input value={thumbSubtitle} onChange={(e) => setThumbSubtitle(e.target.value)} maxLength={200} className="mt-1" />
                      </label>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {thumbBenefits.map((b, i) => (
                        <label key={i} className="block text-sm">
                          <span className="text-muted-foreground">Beneficio {i + 1}</span>
                          <Input
                            value={b}
                            onChange={(e) =>
                              setThumbBenefits((prev) => prev.map((p, idx) => (idx === i ? e.target.value : p)))
                            }
                            maxLength={80}
                            className="mt-1"
                          />
                        </label>
                      ))}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <label className="block text-sm">
                        <span className="text-muted-foreground">Banner CTA</span>
                        <Input value={thumbCta} onChange={(e) => setThumbCta(e.target.value)} maxLength={200} className="mt-1" />
                      </label>
                      <label className="block text-sm">
                        <span className="text-muted-foreground">Estilo</span>
                        <Select value={thumbStyle} onChange={(e) => setThumbStyle(e.target.value as ThumbnailContentStyle | "")} className="mt-1">
                          <option value="">Sin estilo específico</option>
                          {THUMBNAIL_CONTENT_STYLES.map((s) => (
                            <option key={s.value} value={s.value}>{s.label}</option>
                          ))}
                        </Select>
                      </label>
                      <label className="block text-sm">
                        <span className="text-muted-foreground">Formato</span>
                        <Select value={thumbFormat} onChange={(e) => setThumbFormat(e.target.value as ThumbnailFormat)} className="mt-1">
                          <option value="vertical">Vertical (Reel/Historia)</option>
                          <option value="facebook_horizontal">Facebook (1200x630)</option>
                        </Select>
                      </label>
                    </div>
                    {thumbError && (
                      <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                        {thumbError}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button type="submit" disabled={thumbBusy || !thumbTitle.trim()}>
                        {thumbBusy ? "Generando…" : "Generar miniatura con IA"}
                      </Button>
                      <Button type="button" variant="outline" onClick={() => setThumbnail(null)}>
                        Omitir miniatura
                      </Button>
                    </div>
                  </form>
                )}
              </CardContent>
            </Card>
          )}

          {/* Generar texto con IA a partir de un título/tema */}
          {asset && (
            <Card>
              <CardHeader>
                <CardTitle className="text-foreground text-base">Generar texto con IA</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={onGenerateCopy} className="space-y-3">
                  <label className="block text-sm">
                    <span className="text-muted-foreground">
                      Título o tema de la publicación
                    </span>
                    <Input
                      value={aiTopic}
                      onChange={(e) => setAiTopic(e.target.value)}
                      placeholder="Ej: Bowl de salmón teriyaki bajo en carbohidratos"
                      maxLength={1000}
                      className="mt-1"
                    />
                  </label>
                  {aiError && (
                    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {aiError}
                    </div>
                  )}
                  <Button type="submit" disabled={aiBusy || !aiTopic.trim() || !brandId} variant="outline">
                    {aiBusy ? "Escribiendo…" : "Generar caption + CTA + hashtags con IA"}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    La IA completa el título, caption, CTA y exactamente 5 hashtags abajo — sin
                    pasar de 200 palabras entre caption y CTA. Podés editarlos antes de publicar.
                  </p>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Paso 4: publicación */}
          {asset && (
            <Card>
              <CardHeader>
                <CardTitle className="text-foreground text-base">4. Publicación</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={onPublish} className="space-y-4">
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Título interno</span>
                    <Input required value={contentTitle} onChange={(e) => setContentTitle(e.target.value)} className="mt-1" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Caption</span>
                    <Textarea value={caption} onChange={(e) => setCaption(e.target.value)} className="mt-1" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">CTA</span>
                    <Input value={cta} onChange={(e) => setCta(e.target.value)} className="mt-1" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Hashtags (máx. 5, separados por espacio o coma)</span>
                    <Input value={hashtagsRaw} onChange={(e) => setHashtagsRaw(e.target.value)} className="mt-1" />
                    <div className="mt-1 flex flex-wrap gap-1">
                      {hashtags.map((h) => (<Badge key={h} variant="outline">{h}</Badge>))}
                    </div>
                  </label>
                  <p className={`text-xs ${overWordLimit ? "text-destructive" : "text-muted-foreground"}`}>
                    Caption + CTA: {wordCount}/{MAX_CAPTION_CTA_WORDS} palabras
                  </p>
                  <p className={`text-xs ${overHashtagLimit ? "text-destructive" : "text-muted-foreground"}`}>
                    Hashtags: {hashtags.length}/{MAX_HASHTAGS}
                  </p>
                  {formError && (
                    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {formError}
                    </div>
                  )}
                  {publishedUrl && (
                    <div className="rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
                      Borrador creado.{" "}
                      <Link href={publishedUrl} className="underline">
                        Ver publicación →
                      </Link>
                    </div>
                  )}
                  <Button
                    type="submit"
                    disabled={submitting || !contentTitle.trim() || !connectionId || overWordLimit || overHashtagLimit}
                  >
                    {submitting ? "Creando…" : "Crear borrador de publicación"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
