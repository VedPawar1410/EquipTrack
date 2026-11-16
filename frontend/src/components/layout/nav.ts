import { CircleAlert, FileText, LayoutDashboard, Package, Factory, Users, Wrench, type LucideIcon } from "lucide-react";

import type { Role } from "@/lib/auth";

export type NavItem = { href: string; label: string; icon: LucideIcon; minRole: Role };

export const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, minRole: "technician" },
  { href: "/equipment", label: "Equipment", icon: Factory, minRole: "technician" },
  { href: "/issues", label: "Issues", icon: CircleAlert, minRole: "technician" },
  { href: "/maintenance", label: "Maintenance", icon: Wrench, minRole: "technician" },
  { href: "/parts", label: "Parts", icon: Package, minRole: "technician" },
  { href: "/documents", label: "Documents", icon: FileText, minRole: "technician" },
  { href: "/users", label: "Users & roles", icon: Users, minRole: "admin" },
];

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
