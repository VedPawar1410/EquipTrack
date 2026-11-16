"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Pill } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { hasRole, useMe } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { useEquipmentNames } from "@/lib/queries";

import { UploadCard } from "./upload-card";

type Doc = Schemas["DocumentOut"];
const indexing = (d: Doc) => !d.is_indexed && !d.index_error;

export function DocumentsPage() {
  const { data: me } = useMe();
  const names = useEquipmentNames();
  const { data: documents, isPending } = useQuery({
    queryKey: ["documents"],
    queryFn: async () => unwrap(await api.GET("/api/v1/documents")),
    // Poll only while something is still being indexed, then stop.
    refetchInterval: (query) => (query.state.data?.some(indexing) ? 2000 : false),
  });
  return (
    <>
      <PageHeader title="Documents" description="Manuals, SOPs and safety guides the AI assistant answers from." />
      <div className="space-y-6">
        {hasRole(me?.role, "supervisor") && <UploadCard />}
        {isPending ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-36" />)}</div>
        ) : !documents?.length ? (
          <EmptyState icon={FileText} title="No documents yet" description="Upload a machine manual so the AI assistant can answer questions about it." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {documents.map((d) => (
              <DocumentCard key={d.id} doc={d} machine={d.equipment_id ? names.get(d.equipment_id) : undefined}
                            canReindex={hasRole(me?.role, "supervisor")} canDelete={hasRole(me?.role, "admin")} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function DocumentCard({ doc, machine, canReindex, canDelete }: { doc: Doc; machine?: string; canReindex: boolean; canDelete: boolean }) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["documents"] });
  const reindex = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/documents/{document_id}/reindex", { params: { path: { document_id: doc.id } } })),
    onSuccess: () => { refresh(); toast.success("Re-indexing started"); },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { response } = await api.DELETE("/api/v1/documents/{document_id}", { params: { path: { document_id: doc.id } } });
      if (!response.ok) throw new Error("Could not delete the document");
    },
    onSuccess: () => { refresh(); toast.success(`${doc.title} deleted`); },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Card className="gap-3 p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-info-soft text-info"><FileText className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium" title={doc.title}>{doc.title}</p>
          <p className="text-xs text-muted-foreground">{doc.doc_type} · {machine ?? "General"}</p>
        </div>
        {doc.is_indexed ? <Pill tone="success">Indexed</Pill> : doc.index_error ? (
          <Tooltip>
            <TooltipTrigger asChild><span><Pill tone="danger">Failed</Pill></span></TooltipTrigger>
            <TooltipContent className="max-w-xs">{doc.index_error}</TooltipContent>
          </Tooltip>
        ) : <Pill tone="warning"><Loader2 className="size-3 animate-spin" /> Indexing</Pill>}
      </div>
      {doc.index_error && <p className="rounded-md bg-danger-soft px-2 py-1.5 text-xs text-danger">{doc.index_error}</p>}
      <p className="text-xs text-muted-foreground">
        {doc.file_size_bytes ? `${Math.max(1, Math.round(doc.file_size_bytes / 1024))} KB · ` : ""}
        uploaded {formatDate(doc.uploaded_at)}{doc.uploaded_by ? ` by ${doc.uploaded_by}` : ""}
      </p>
      <div className="flex gap-1 border-t pt-3">
        <Button asChild size="sm" variant="ghost"><a href={`/api/backend${doc.blob_url}`} target="_blank" rel="noreferrer"><Download className="size-3.5" /> Open</a></Button>
        {canReindex && (
          <Button size="sm" variant="ghost" disabled={reindex.isPending || (!doc.is_indexed && !doc.index_error)} onClick={() => reindex.mutate()}>
            <RefreshCw className="size-3.5" /> Re-index
          </Button>
        )}
        {canDelete && (
          <Dialog>
            <DialogTrigger asChild><Button size="sm" variant="ghost" className="ml-auto text-danger"><Trash2 className="size-3.5" /> Delete</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete {doc.title}?</DialogTitle>
                <DialogDescription>The file and its search index are removed permanently. The AI assistant will no longer use it.</DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
                <DialogClose asChild><Button variant="destructive" onClick={() => remove.mutate()}>Delete</Button></DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </Card>
  );
}
