"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, UserCheck, UserX } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Pill } from "@/components/domain/badges";
import { PageHeader } from "@/components/layout/page-header";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useMe, type Role } from "@/lib/auth";
import { formatDate } from "@/lib/format";

const ROLES: Role[] = ["technician", "supervisor", "admin"];
const ROLE_TONE = { technician: "neutral", supervisor: "info", admin: "warning" } as const;

export function UsersPage() {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const { data: users, isPending } = useQuery({
    queryKey: ["users"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/users")),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const setRole = useMutation({
    mutationFn: async ({ id, role }: { id: string; role: Role }) =>
      unwrap(await api.PATCH("/api/v1/auth/users/{user_id}/role", { params: { path: { user_id: id } }, body: { role } })),
    onSuccess: (u) => { refresh(); toast.success(`${u.username} is now ${u.role}`); },
    onError: (error) => toast.error(error.message),
  });
  const setActive = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) =>
      active
        ? unwrap(await api.PATCH("/api/v1/auth/users/{user_id}/activate", { params: { path: { user_id: id } } }))
        : unwrap(await api.PATCH("/api/v1/auth/users/{user_id}/deactivate", { params: { path: { user_id: id } } })),
    onSuccess: (u) => { refresh(); toast.success(`${u.username} ${u.is_active ? "reactivated" : "deactivated: their sessions stop working now"}`); },
    onError: (error) => toast.error(error.message),
  });

  return (
    <>
      <PageHeader title="Users & roles" description="Accounts are created here: there is no public sign-up." actions={<AddUserDialog onCreated={refresh} />} />
      <Card className="gap-0 p-0">
        {isPending ? <div className="p-4"><Skeleton className="h-48" /></div> : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">User</TableHead><TableHead>Role</TableHead><TableHead>Status</TableHead>
                <TableHead>Created</TableHead><TableHead className="pr-4 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((u: Schemas["UserOut"]) => {
                const self = u.id === me?.id;
                return (
                  <TableRow key={u.id} className={u.is_active ? "" : "opacity-60"}>
                    <TableCell className="pl-4">
                      <div className="flex items-center gap-3">
                        <Avatar className="size-8"><AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">{u.username.slice(0, 2).toUpperCase()}</AvatarFallback></Avatar>
                        <div><p className="font-medium">{u.username}{self && <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>}</p><p className="text-xs text-muted-foreground">{u.email}</p></div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {self ? <Pill tone={ROLE_TONE[u.role]} className="capitalize">{u.role}</Pill> : (
                        <Select value={u.role} onValueChange={(role) => setRole.mutate({ id: u.id, role: role as Role })}>
                          <SelectTrigger size="sm" className="w-36 capitalize" aria-label={`Role for ${u.username}`}><SelectValue /></SelectTrigger>
                          <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}</SelectContent>
                        </Select>
                      )}
                    </TableCell>
                    <TableCell><Pill tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Deactivated"}</Pill></TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(u.created_at)}</TableCell>
                    <TableCell className="pr-4 text-right">
                      {self ? <span className="text-xs text-muted-foreground">You can&apos;t change your own account here</span> : u.is_active ? (
                        <Button size="sm" variant="ghost" className="text-danger" onClick={() => setActive.mutate({ id: u.id, active: false })}><UserX className="size-3.5" /> Deactivate</Button>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={() => setActive.mutate({ id: u.id, active: true })}><UserCheck className="size-3.5" /> Reactivate</Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  );
}

function AddUserDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<Role>("technician");
  const create = useMutation({
    mutationFn: async (body: Schemas["UserCreate"]) => unwrap(await api.POST("/api/v1/auth/users", { body })),
    onSuccess: (u) => { onCreated(); toast.success(`${u.username} created. Share the temporary password with them privately.`); setOpen(false); setRole("technician"); },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button><Plus className="size-4" /> Add user</Button></DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a user</DialogTitle>
          <DialogDescription>They sign in with this username and can change the temporary password from their account.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          create.mutate({ username: String(f.get("username")).trim(), email: String(f.get("email")).trim(), password: String(f.get("password")), role });
        }}>
          <div className="space-y-2"><Label htmlFor="new-username">Username</Label><Input id="new-username" name="username" required minLength={3} maxLength={50} pattern="[A-Za-z0-9._\-]+" title="Letters, digits, dot, underscore and hyphen" /></div>
          <div className="space-y-2"><Label htmlFor="new-email">Email</Label><Input id="new-email" name="email" type="email" required maxLength={100} /></div>
          <div className="space-y-2"><Label htmlFor="new-password">Temporary password</Label><Input id="new-password" name="password" type="password" required minLength={8} autoComplete="new-password" /></div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={role} onValueChange={(r) => setRole(r as Role)}>
              <SelectTrigger className="w-full capitalize"><SelectValue /></SelectTrigger>
              <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={create.isPending}>{create.isPending && <Loader2 className="size-4 animate-spin" />} Create user</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
