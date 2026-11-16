import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Parts" };

export default function Page() {
  return <PageHeader title="Parts" description="Spare parts stock and reorder levels." />;
}
