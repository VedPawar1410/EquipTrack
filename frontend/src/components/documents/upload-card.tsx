"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, Loader2, X } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DOC_TYPES } from "@/lib/enums";
import { useEquipmentList } from "@/lib/queries";
import { cn } from "@/lib/utils";

const MAX_MB = 10;
const ACCEPT = ".pdf,.txt,.md,application/pdf,text/plain,text/markdown";
const GENERAL = "general";

/** Supervisors upload manuals; the API stores them and indexes them for the AI assistant in the background. */
export function UploadCard() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [docType, setDocType] = useState("");
  const [machine, setMachine] = useState(GENERAL);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { data: equipment = [] } = useEquipmentList();

  const upload = useMutation({
    mutationFn: async (form: FormData) => {
      // Multipart goes through the same cookie proxy; plain fetch keeps the browser-set boundary header.
      const response = await fetch("/api/backend/api/v1/documents/upload", { method: "POST", body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Upload failed");
      return body;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Uploaded: indexing has started");
      setFile(null);
      setDocType("");
      setMachine(GENERAL);
    },
    onError: (error) => toast.error(error.message),
  });

  function choose(next: File | undefined) {
    if (!next) return;
    if (next.size > MAX_MB * 1024 * 1024) return toast.error(`That file is over ${MAX_MB} MB`);
    setFile(next);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a manual</CardTitle>
        <CardDescription>PDF, .txt or .md up to {MAX_MB} MB. It becomes searchable by the AI assistant once indexed.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 md:grid-cols-[1.2fr_1fr]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            const form = new FormData(e.currentTarget);
            form.set("file", file);
            form.set("doc_type", docType);
            if (machine !== GENERAL) form.set("equipment_id", machine); else form.delete("equipment_id");
            upload.mutate(form);
          }}
        >
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]); }}
            className={cn(
              "flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors",
              dragging ? "border-primary bg-primary/5" : "hover:border-primary/50 hover:bg-muted/50",
            )}
          >
            <FileUp className="size-7 text-muted-foreground" />
            {file ? (
              <span className="flex items-center gap-2 text-sm font-medium">
                {file.name} · {(file.size / 1024).toFixed(0)} KB
                <X className="size-4 text-muted-foreground" aria-label="Remove file" onClick={(e) => { e.stopPropagation(); setFile(null); }} />
              </span>
            ) : (
              <span className="text-sm text-muted-foreground"><span className="font-medium text-foreground">Drop a file here</span> or click to choose</span>
            )}
            <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => choose(e.target.files?.[0])} />
          </button>
          <div className="grid gap-3">
            <div className="space-y-2"><Label htmlFor="doc-title">Title</Label><Input id="doc-title" name="title" required maxLength={100} placeholder="TL-300 Service Manual" /></div>
            <div className="space-y-2">
              <Label>Document type</Label>
              <Select value={docType} onValueChange={setDocType}>
                <SelectTrigger className="w-full"><SelectValue placeholder="Manual, SOP, safety guide…" /></SelectTrigger>
                <SelectContent className="max-h-72">{DOC_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Machine</Label>
              <Select value={machine} onValueChange={setMachine}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent className="max-h-72">
                  <SelectItem value={GENERAL}>General (all machines)</SelectItem>
                  {equipment.filter((e) => e.status !== "retired").map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={!file || !docType || upload.isPending}>
              {upload.isPending && <Loader2 className="size-4 animate-spin" />} Upload
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
