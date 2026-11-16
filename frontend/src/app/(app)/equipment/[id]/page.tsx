import type { Metadata } from "next";
import { Suspense } from "react";

import { EquipmentDetail } from "@/components/equipment/equipment-detail";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Equipment detail" };

// Not async on purpose: the route param is request-time data. Awaiting it here would stop the whole
// page from prerendering; resolving it inside Suspense keeps the frame in the static shell and only
// the id-specific part streams in.
export default function Page({ params }: PageProps<"/equipment/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      {params.then(({ id }) => <EquipmentDetail id={id} />)}
    </Suspense>
  );
}
