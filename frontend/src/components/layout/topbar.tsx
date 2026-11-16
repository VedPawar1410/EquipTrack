"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useHydrated } from "@/hooks/use-hydrated";
import { api, unwrap } from "@/lib/api/client";
import { signOut, useMe } from "@/lib/auth";

import { SidebarContent, initials } from "./sidebar";
import { ThemeToggle } from "./theme-toggle";

function Notifications() {
  // Unresolved critical issues: the one thing worth interrupting anyone for.
  const hydrated = useHydrated();
  const { data = [] } = useQuery({
    queryKey: ["issues", "critical"],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues/critical")),
    refetchInterval: 60_000,
  });
  const critical = hydrated ? data : []; // see useHydrated
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={`Notifications: ${critical.length} critical issues`}>
          <Bell className="size-4.5" />
          {critical.length > 0 && (
            <span className="absolute top-1.5 right-1.5 flex size-4 items-center justify-center rounded-full bg-danger text-[10px] font-semibold text-white">
              {critical.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Critical issues</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {critical.length === 0 && <p className="px-2 py-3 text-sm text-muted-foreground">Nothing critical right now.</p>}
        {critical.slice(0, 6).map((issue) => (
          <DropdownMenuItem key={issue.id} asChild>
            <Link href="/issues" className="flex flex-col items-start gap-0.5">
              <span className="font-medium">{issue.title}</span>
              <span className="text-xs text-muted-foreground">
                {issue.status}
                {issue.error_code ? ` · ${issue.error_code}` : ""}
              </span>
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function Topbar() {
  const router = useRouter();
  const { data: me } = useMe();
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md sm:px-6">
      <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setMenuOpen(true)}>
        <Menu className="size-5" />
      </Button>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarContent onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <form
        className="relative max-w-md flex-1"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const q = new FormData(e.currentTarget).get("q")?.toString().trim();
          router.push(q ? `/equipment?search=${encodeURIComponent(q)}` : "/equipment");
        }}
      >
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input name="q" placeholder="Search equipment…" className="h-9 bg-card pl-9" aria-label="Search equipment" />
      </form>

      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        <Notifications />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="ml-1 h-9 gap-2 px-1.5" aria-label="Account menu">
              <Avatar className="size-7">
                <AvatarFallback className="bg-primary/10 text-[11px] font-semibold text-primary">
                  {me ? initials(me.username) : "··"}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <p className="font-medium">{me?.username}</p>
              <p className="text-xs text-muted-foreground">{me?.email}</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => signOut()}>
              <LogOut className="size-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
