"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, X } from "lucide-react";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/feedback/spinner";
import { useConstants } from "@/hooks/use-constants";
import { ApiError } from "@/lib/api/client";
import { evidenceEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { fmtBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

const uploadSchema = z.object({
  evidence_title: z.string().min(2, "Required."),
  doc_type: z.string().min(2, "Pick a type."),
  notes: z.string().optional(),
});
type UploadForm = z.infer<typeof uploadSchema>;

export function UploadDropzone({ caseId }: { caseId: number }) {
  const qc = useQueryClient();
  const constants = useConstants();
  const [file, setFile] = useState<File | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<UploadForm>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { evidence_title: "", doc_type: "", notes: "" },
  });

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    if (!form.getValues("evidence_title")) {
      form.setValue("evidence_title", f.name.replace(/\.pdf$/i, ""));
    }
  }, [form]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    maxSize: 25 * 1024 * 1024,
  });

  const mutation = useMutation({
    mutationFn: (body: UploadForm) =>
      evidenceEndpoints.upload(caseId, {
        file: file!,
        evidence_title: body.evidence_title,
        doc_type: body.doc_type,
        notes: body.notes || undefined,
      }),
    onMutate: () => setServerError(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.evidenceDocuments(caseId) });
      setFile(null);
      form.reset({ evidence_title: "", doc_type: "", notes: "" });
    },
    onError: (err) =>
      setServerError(err instanceof ApiError ? err.message : "Upload failed."),
  });

  const onSubmit = form.handleSubmit((v) => {
    if (!file) {
      setServerError("Pick a PDF first.");
      return;
    }
    mutation.mutate(v);
  });

  return (
    <form className="space-y-5" onSubmit={onSubmit} noValidate>
      <div
        {...getRootProps({
          className: cn(
            "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-6 py-10 text-center transition-colors",
            isDragActive
              ? "border-accent bg-accent-wash/60"
              : "border-rule bg-parchment-soft/50 hover:border-accent/60 hover:bg-parchment-soft",
          ),
        })}
      >
        <input {...getInputProps()} />
        <FileUp className="h-5 w-5 text-accent" />
        <div className="font-display text-base text-ink">
          {file ? file.name : isDragActive ? "Drop the PDF" : "Drop a PDF or click to browse"}
        </div>
        <p className="text-xs text-ink-mute">
          PDF only · max 25 MB · single file per upload
        </p>
        {file && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setFile(null);
            }}
            className="mt-2 inline-flex items-center gap-1 text-xs text-ink-mute hover:text-ink"
          >
            <X className="h-3 w-3" /> Remove ({fmtBytes(file.size)})
          </button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="evidence_title">Evidence title</Label>
          <Input
            id="evidence_title"
            placeholder="e.g. FIR — Bandra Police Station"
            {...form.register("evidence_title")}
          />
          {form.formState.errors.evidence_title && (
            <p className="text-xs text-danger">
              {form.formState.errors.evidence_title.message}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="doc_type">Evidence type</Label>
          <Controller
            control={form.control}
            name="doc_type"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="doc_type">
                  <SelectValue placeholder="Choose…" />
                </SelectTrigger>
                <SelectContent>
                  {(constants.data?.evidence_doc_types ?? []).map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {form.formState.errors.doc_type && (
            <p className="text-xs text-danger">{form.formState.errors.doc_type.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="notes">Notes (optional)</Label>
        <Textarea id="notes" rows={2} placeholder="Source, context, witness." {...form.register("notes")} />
      </div>

      {serverError && <p className="text-sm text-danger">{serverError}</p>}

      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={mutation.isPending || !file}>
          {mutation.isPending && <Spinner />}
          Ingest evidence
        </Button>
      </div>
    </form>
  );
}
