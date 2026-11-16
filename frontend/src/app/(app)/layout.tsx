import { Suspense } from "react";

import { AssistantProvider } from "@/components/assistant/assistant-context";
import { AssistantLauncher } from "@/components/assistant/assistant-launcher";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

/**
 * Every signed-in page: fixed sidebar on large screens, a slide-out menu on small ones, and the AI
 * assistant as a floating button that opens a side panel.
 * Sidebar, top bar and launcher read the URL (usePathname / useRouter), which only exists at request time,
 * so they sit in Suspense boundaries: the rest of the page shell can still prerender, and the URL-aware
 * parts stream in. The fallbacks are same-size empty frames, so nothing shifts when they arrive.
 */
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <AssistantProvider>
      <div className="min-h-screen">
        <Suspense fallback={<aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-sidebar lg:block" />}>
          <Sidebar />
        </Suspense>
        <div className="lg:pl-64">
          <Suspense fallback={<div className="sticky top-0 h-16 border-b bg-background/80" />}>
            <Topbar />
          </Suspense>
          {/* pb-24 keeps page content clear of the floating assistant button */}
          <main className="mx-auto w-full max-w-7xl px-4 py-6 pb-24 sm:px-6 lg:px-8">{children}</main>
        </div>
        <Suspense>
          <AssistantLauncher />
        </Suspense>
      </div>
    </AssistantProvider>
  );
}
