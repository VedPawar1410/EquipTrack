"use client";

import { SupervisorDashboard } from "@/components/dashboard/supervisor-dashboard";
import { TechnicianDashboard } from "@/components/dashboard/technician-dashboard";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useClientHour } from "@/hooks/use-client-hour";
import { hasRole, useMe } from "@/lib/auth";

function greetingFor(hour: number | null) {
  if (hour === null) return "Welcome";
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default function DashboardPage() {
  const { data: me } = useMe();
  const greeting = greetingFor(useClientHour());
  const supervisor = hasRole(me?.role, "supervisor");
  return (
    <>
      <PageHeader
        title={me ? `${greeting}, ${me.username}` : "Dashboard"}
        description={supervisor ? "Here's what needs attention across the plant." : "Your work queue for today."}
      />
      {!me ? <Skeleton className="h-96" /> : supervisor ? <SupervisorDashboard /> : <TechnicianDashboard username={me.username} />}
    </>
  );
}
