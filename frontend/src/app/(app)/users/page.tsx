import type { Metadata } from "next";

import { RequireRole } from "@/components/layout/require-role";
import { UsersPage } from "@/components/users/users-page";

export const metadata: Metadata = { title: "Users & roles" };

export default function Page() {
  return (
    <RequireRole minimum="admin">
      <UsersPage />
    </RequireRole>
  );
}
