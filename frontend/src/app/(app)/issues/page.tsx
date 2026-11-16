import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Issues" };

export default function Page() {
  return <PageHeader title="Issues" description="Report, claim, resolve and close equipment issues." />;
}
