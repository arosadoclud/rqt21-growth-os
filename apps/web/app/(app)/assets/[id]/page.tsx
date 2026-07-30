"use client";

import { useParams } from "next/navigation";

import { AssetDetail } from "@/components/assets/asset-detail";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  return <AssetDetail assetId={params.id} />;
}
