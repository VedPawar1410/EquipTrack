import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Documents" };

export default function Page() {
  return <PageHeader title="Documents" description="Manuals, SOPs and safety guides the AI assistant answers from." />;
}
