import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Maintenance" };

export default function Page() {
  return <PageHeader title="Maintenance" description="Upcoming and overdue service, and the maintenance log." />;
}
