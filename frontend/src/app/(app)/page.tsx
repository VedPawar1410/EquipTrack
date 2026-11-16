"use client";

import { PageHeader } from "@/components/layout/page-header";
import { useClientHour } from "@/hooks/use-client-hour";
import { useMe } from "@/lib/auth";

function greetingFor(hour: number | null) {
  if (hour === null) return "Welcome";
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default function DashboardPage() {
  const { data: me } = useMe();
  const greeting = greetingFor(useClientHour());
  return (
    <PageHeader
      title={me ? `${greeting}, ${me.username}` : "Dashboard"}
      description="Here's what needs attention across the plant."
    />
  );
}
