import type { Metadata } from "next";

import { IssuesBoard } from "@/components/issues/issues-board";

export const metadata: Metadata = { title: "Issues" };

export default function Page() {
  return <IssuesBoard />;
}
