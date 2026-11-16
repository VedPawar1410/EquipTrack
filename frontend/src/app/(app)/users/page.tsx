import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";
import { RequireRole } from "@/components/layout/require-role";

export const metadata: Metadata = { title: "Users & roles" };

export default function Page() {
  return (
    <RequireRole minimum="admin">
      <PageHeader title="Users & roles" description="Accounts, roles and access." />
    </RequireRole>
  );
}
