import type { Metadata } from "next";

import { PartsPage } from "@/components/parts/parts-page";

export const metadata: Metadata = { title: "Parts" };

export default function Page() {
  return <PartsPage />;
}
