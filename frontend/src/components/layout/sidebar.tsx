"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { useHydrated } from "@/hooks/use-hydrated";
import { hasRole, useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { Logo } from "./logo";
import { NAV, isActive } from "./nav";

export function initials(name: string) {
  return name.slice(0, 2).toUpperCase();
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const hydrated = useHydrated();
  const { data } = useMe();
  const me = hydrated ? data : undefined; // see useHydrated
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-0.5 px-3 py-2" aria-label="Main">
        {NAV.filter((item) => hasRole(me?.role, item.minRole)).map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className={cn("size-4.5", active ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        {me ? (
          <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
            <Avatar className="size-8">
              <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">{initials(me.username)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{me.username}</p>
              <p className="text-xs capitalize text-muted-foreground">{me.role}</p>
            </div>
          </div>
        ) : (
          <Skeleton className="h-11 w-full" />
        )}
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-sidebar-border bg-sidebar lg:block">
      <SidebarContent />
    </aside>
  );
}
