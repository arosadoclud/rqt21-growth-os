"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type {
  Asset,
  AssetVariant,
  ThumbnailContentStyle,
  ThumbnailFormat,
  VariantType,
} from "@rqt21/contracts";
import { VARIANT_TYPES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const THUMBNAIL_CONTENT_STYLES: { value: ThumbnailContentStyle; label: string }[] = [
  { value: "receta", label: "Receta" },
  { value: "curiosidad", label: "Curiosidad" },
  { value: "encuesta", label: "Encuesta" },
  { value: "antes_despues", label: "Antes / Después" },
  { value: "receta_rapida", label: "Receta rápida" },
  { value: "educativo", label: "Educativo" },
];

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const assetId = params.id;
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);
  const canDownload = org?.role !== "ANALYST" && org?.role !== "VIEWER";

  const [asset, setAsset] = useState<Asset | null>(null);
  const [variants, setVariants] = useState<AssetVariant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);

  const [platform, setPlatform] = useState("INSTAGRAM");
  const [variantType, setVariantType] = useState<VariantType>("STORY");
  const [width, setWidth] = useState("1080");
  const [height, setHeight] = useState("1920");

  const [thumbTitle, setThumbTitle] = useState("");
  const [thumbSubtitle, setThumbSubtitle] = useState("");
  const [thumbBenefits, setThumbBenefits] = useState(["", "", ""]);
  const [thumbCta, setThumbCta] = useState("");
  const [thumbStyle, setThumbStyle] = useState<ThumbnailContentStyle | "">("");
  const [thumbFormat, setThumbFormat] = useState<ThumbnailFormat>("vertical");
  const [thumbBusy, setThumbBusy] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId || !assetId) return;
    setLoading(true);
    setError(null);
    try {
      const [a, v] = await Promise.all([
        api.getAsset(currentOrgId, assetId),
        api.listAssetVariants(currentOrgId, assetId),
      ]);
      setAsset(a);
      setVariants(v);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar el activo");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, assetId]);

  useEffect(() => {
    void load();
  }, [load]);

  const archive = async () => {
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    try {
      await api.archiveAsset(currentOrgId, assetId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al archivar");
    } finally {
      setBusy(false);
    }
  };

  const getDownloadUrl = async () => {
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    setSignedUrl(null);
    try {
      const res = await api.assetDownloadUrl(currentOrgId, assetId);
      setSignedUrl(res.url);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al generar URL firmada");
    } finally {
      setBusy(false);
    }
  };

  const createVariant = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !assetId) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAssetVariant(currentOrgId, assetId, {
        platform,
        variant_type: variantType,
        width: Number(width) || null,
        height: Number(height) || null,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al crear variante");
    } finally {
      setBusy(false);
    }
  };

  const generateThumbnail = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !assetId) return;
    setThumbBusy(true);
    setThumbError(null);
    try {
      await api.generateThumbnail(currentOrgId, assetId, {
        title: thumbTitle,
        subtitle: thumbSubtitle || null,
        benefits: thumbBenefits.map((b) => b.trim()).filter(Boolean),
        cta_banner: thumbCta || null,
        content_style: thumbStyle || null,
        format: thumbFormat,
      });
      await load();
    } catch (err) {
      setThumbError(err instanceof ApiError ? err.detail : "Error al generar la miniatura");
    } finally {
      setThumbBusy(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;
  if (loading && !asset) return <p className="text-sm text-muted-foreground">Cargando…</p>;
  if (!asset) return <p className="text-sm text-muted-foreground">Activo no encontrado.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{asset.original_filename}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {asset.asset_type} · {asset.status} · {(asset.size_bytes / 1024).toFixed(0)} KB · {formatDate(asset.created_at)}
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Dimensiones</div>
            <div className="text-sm font-medium">
              {asset.width && asset.height ? `${asset.width}x${asset.height}` : "—"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Duración</div>
            <div className="text-sm font-medium">{asset.duration_seconds ?? "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Checksum SHA-256</div>
            <div className="truncate text-xs font-mono">{asset.checksum_sha256 || "—"}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="space-y-2 p-4 text-sm">
          <p><strong>Texto alternativo:</strong> {asset.alt_text || "— (requerido para publicar en Instagram)"}</p>
          <p><strong>Caption:</strong> {asset.caption || "—"}</p>
          {typeof asset.metadata?.duplicate_of === "string" && (
            <p className="text-warning">Duplicado de otro activo: {asset.metadata.duplicate_of as string}</p>
          )}
        </CardContent>
      </Card>

      {canWrite && asset.status !== "ARCHIVED" && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void archive()} disabled={busy}>
            Archivar
          </Button>
          {canDownload && asset.status === "READY" && (
            <Button variant="outline" onClick={() => void getDownloadUrl()} disabled={busy}>
              Generar URL firmada
            </Button>
          )}
        </div>
      )}

      {signedUrl && (
        <div className="rounded-md border border-border bg-muted px-3 py-2 text-xs font-mono break-all">
          {signedUrl}
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight">Variantes</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Plataforma</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Dimensiones</TableHead>
                <TableHead>Estado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {variants.length === 0 && (
                <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin variantes</TableCell></TableRow>
              )}
              {variants.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>{v.platform}</TableCell>
                  <TableCell className="text-muted-foreground">{v.variant_type}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {v.width && v.height ? `${v.width}x${v.height}` : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{v.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>

        {canWrite && asset.status === "READY" && asset.asset_type === "VIDEO" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-sm">Generar miniatura con IA</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={generateThumbnail} className="space-y-4">
                {thumbError && (
                  <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {thumbError}
                  </div>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Título *</span>
                    <Input
                      value={thumbTitle}
                      onChange={(e) => setThumbTitle(e.target.value)}
                      required
                      maxLength={200}
                      className="mt-1"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Subtítulo</span>
                    <Input
                      value={thumbSubtitle}
                      onChange={(e) => setThumbSubtitle(e.target.value)}
                      maxLength={200}
                      className="mt-1"
                    />
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
                    <Input
                      value={thumbCta}
                      onChange={(e) => setThumbCta(e.target.value)}
                      maxLength={200}
                      className="mt-1"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Estilo</span>
                    <Select
                      value={thumbStyle}
                      onChange={(e) => setThumbStyle(e.target.value as ThumbnailContentStyle | "")}
                      className="mt-1"
                    >
                      <option value="">Sin estilo específico</option>
                      {THUMBNAIL_CONTENT_STYLES.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </Select>
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Formato</span>
                    <Select
                      value={thumbFormat}
                      onChange={(e) => setThumbFormat(e.target.value as ThumbnailFormat)}
                      className="mt-1"
                    >
                      <option value="vertical">Vertical (Reel/Historia)</option>
                      <option value="facebook_horizontal">Facebook (1200x630)</option>
                    </Select>
                  </label>
                </div>
                <Button type="submit" disabled={thumbBusy || !thumbTitle.trim()}>
                  {thumbBusy ? "Generando…" : "Generar miniatura con IA"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {canWrite && asset.status === "READY" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-foreground text-sm">Nueva variante (MOCK)</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={createVariant} className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-4">
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Plataforma</span>
                    <Input value={platform} onChange={(e) => setPlatform(e.target.value)} className="mt-1" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Tipo</span>
                    <Select value={variantType} onChange={(e) => setVariantType(e.target.value as VariantType)} className="mt-1">
                      {VARIANT_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
                    </Select>
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Ancho</span>
                    <Input value={width} onChange={(e) => setWidth(e.target.value)} className="mt-1" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-muted-foreground">Alto</span>
                    <Input value={height} onChange={(e) => setHeight(e.target.value)} className="mt-1" />
                  </label>
                </div>
                <Button type="submit" disabled={busy}>
                  Crear variante
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
