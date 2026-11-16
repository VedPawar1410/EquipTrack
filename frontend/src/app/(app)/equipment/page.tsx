import type { Metadata } from "next";
import { Suspense } from "react";

import { EquipmentList } from "@/components/equipment/equipment-list";

export const metadata: Metadata = { title: "Equipment" };

// useSearchParams needs a Suspense boundary so the rest of the page can prerender.
export default function Page() {
  return <Suspense><EquipmentList /></Suspense>;
}
