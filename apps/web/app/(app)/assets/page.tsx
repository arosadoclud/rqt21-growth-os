"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Asset, AssetStatus, AssetType, Brand } from "@rqt21/contracts";
import { ASSET_STATUSES, ASSET_TYPES } from "@rqt21/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth, formatDate } from "@/lib/ui";

const STATUS_VARIANT: Record<AssetStatus, "secondary" | "warning" | "success" | "destructive"> = {
  UPLOADING: "secondary",
  PROCESSING: "warning",
  READY: "success",
  REJECTED: "destructive",
  FAILED: "destructive",
  ARCHIVED: "secondary",
};

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

export default function AssetsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Asset[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<AssetType | "">("");
  const [statusFilter, setStatusFilter] = useState<AssetStatus | "">("");

  const [file, setFile] = useState<File | null>(null);
  const [brandId, setBrandId] = useState("");
  const [altText, setAltText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (typeFilter) params.asset_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      const [a, bs] = await Promise.all([
        api.listAssets(currentOrgId, params),
        api.listBrands(currentOrgId),
      ]);
      setItems(a);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar activos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, typeFilter, statusFilter, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const detectType = (f: File): AssetType => {
    if (f.type.startsWith("image/")) return "IMAGE";
    if (f.type.startsWith("video/")) return "VIDEO";
    if (f.type.startsWith("audio/")) return "AUDIO";
    if (f.type === "application/pdf") return "DOCUMENT";
    return "OTHER";
  };

  const onUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const init = await api.initUpload(currentOrgId, {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        asset_type: detectType(file),
        brand_id: brandId || null,
        alt_text: altText || null,
      });
      const content_base64 = await fileToBase64(file);
      await api.completeUpload(currentOrgId, { asset_id: init.asset_id, content_base64 });
      setFile(null);
      setAltText("");
      await load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.detail : "Error al subir el activo");
    } finally {
      setUploading(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Biblioteca de activos</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as AssetType | "")} className="w-48">
          <option value="">Todos los tipos</option>
          {ASSET_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </Select>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as AssetStatus | "")} className="w-48">
          <option value="">Todos los estados</option>
          {ASSET_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Archivo</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Tamaño</TableHead>
              <TableHead>Subido</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Sin activos</TableCell></TableRow>
            )}
            {items.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Link href={`/assets/${a.id}`} className="text-primary hover:underline">
                    {a.original_filename}
                  </Link>
                  {!a.alt_text && a.asset_type === "IMAGE" && (
                    <Badge variant="warning" className="ml-2">sin alt text</Badge>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{a.asset_type}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[a.status]}>{a.status}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{(a.size_bytes / 1024).toFixed(0)} KB</TableCell>
                <TableCell className="text-muted-foreground">{formatDate(a.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Subir activo (simulado, MOCK)</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onUpload} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    <option value="">Sin marca</option>
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Archivo</span>
                  <input
                    type="file"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="mt-1 w-full text-sm"
                  />
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Texto alternativo (obligatorio para imágenes en publicaciones)</span>
                  <Input value={altText} onChange={(e) => setAltText(e.target.value)} className="mt-1" />
                </label>
              </div>
              {uploadError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {uploadError}
                </div>
              )}
              <Button type="submit" disabled={uploading || !file}>
                {uploading ? "Subiendo…" : "Subir"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
