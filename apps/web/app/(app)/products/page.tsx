"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Brand, Product, ProductStatus } from "@rqt21/contracts";
import { PRODUCT_STATUSES } from "@rqt21/contracts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canWriteGrowth } from "@/lib/ui";

export default function ProductsPage() {
  const { currentOrgId, organizations } = useAuth();
  const org = organizations.find((o) => o.id === currentOrgId);
  const canWrite = canWriteGrowth(org?.role);

  const [items, setItems] = useState<Product[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [brandId, setBrandId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState<ProductStatus>("DRAFT");
  const [checkout, setCheckout] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!currentOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const [ps, bs] = await Promise.all([
        api.listProducts(currentOrgId),
        api.listBrands(currentOrgId),
      ]);
      setItems(ps);
      setBrands(bs);
      if (!brandId && bs.length > 0) setBrandId(bs[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar productos");
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, brandId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentOrgId || !brandId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createProduct(currentOrgId, {
        brand_id: brandId,
        name,
        slug,
        price: price || null,
        status,
        checkout_url: checkout || null,
      });
      setName("");
      setSlug("");
      setPrice("");
      setCheckout("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error creando producto");
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentOrgId) return <p className="text-sm text-muted-foreground">Selecciona una organización.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Productos</h1>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Precio</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Checkout</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Cargando…</TableCell></TableRow>
            )}
            {!loading && items.length === 0 && (
              <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Sin productos</TableCell></TableRow>
            )}
            {items.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {p.price ? `${p.price} ${p.currency}` : "—"}
                </TableCell>
                <TableCell className="text-muted-foreground">{p.status}</TableCell>
                <TableCell className="max-w-xs truncate text-muted-foreground">
                  {p.checkout_url || "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {canWrite && brands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground text-lg">Nuevo producto</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="text-muted-foreground">Marca</span>
                  <Select value={brandId} onChange={(e) => setBrandId(e.target.value)} className="mt-1">
                    {brands.map((b) => (<option key={b.id} value={b.id}>{b.name}</option>))}
                  </Select>
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Nombre</span>
                  <Input required value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Slug</span>
                  <Input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={(e) => setSlug(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Precio (USD)</span>
                  <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} className="mt-1" />
                </label>
                <label className="block text-sm">
                  <span className="text-muted-foreground">Estado</span>
                  <Select value={status} onChange={(e) => setStatus(e.target.value as ProductStatus)} className="mt-1">
                    {PRODUCT_STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
                  </Select>
                </label>
                <label className="block text-sm sm:col-span-2">
                  <span className="text-muted-foreground">Checkout URL</span>
                  <Input type="url" value={checkout} onChange={(e) => setCheckout(e.target.value)} className="mt-1" />
                </label>
              </div>
              {formError && (
                <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Guardando…" : "Crear producto"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
