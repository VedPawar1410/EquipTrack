import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Equipment" };

export default function Page() {
  return <PageHeader title="Equipment" description="Every machine in the plant, its status and health." />;
}
