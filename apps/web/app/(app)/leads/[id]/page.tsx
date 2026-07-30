"use client";

import { useParams } from "next/navigation";

import { LeadProfile } from "@/components/leads/lead-profile";

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  return <LeadProfile leadId={params.id} />;
}
