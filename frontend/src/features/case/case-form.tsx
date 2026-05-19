"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";

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
import { caseEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { caseSchema, type CaseInput } from "@/lib/validation/case";

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (days: number) =>
  new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

export function CaseForm({ firstCase = false }: { firstCase?: boolean }) {
  const router = useRouter();
  const qc = useQueryClient();
  const constants = useConstants();
  const form = useForm<CaseInput>({
    resolver: zodResolver(caseSchema),
    defaultValues: {
      case_name: "",
      case_type: "",
      court_or_forum: "",
      jurisdiction: "",
      client_name: "",
      party_names: "",
      your_role_in_case: "",
      opposing_party_name: "",
      filing_date: today(),
      next_hearing_date: addDays(21),
      urgency_level: "Routine",
      confidentiality_level: "Standard",
      case_status: "Drafting",
      short_case_summary: "",
      internal_notes: "",
    },
  });

  const mutation = useMutation({
    mutationFn: caseEndpoints.create,
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: qk.cases });
      router.replace(`/cases/${created.id}`);
    },
    onError: (err) => {
      form.setError("root", {
        message: err instanceof ApiError ? err.message : "Failed to create case.",
      });
    },
  });

  if (!constants.data) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Spinner /> Loading form options…
      </div>
    );
  }
  const C = constants.data;

  return (
    <form
      className="space-y-6"
      onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
      noValidate
    >
      <div className="grid gap-5 md:grid-cols-2">
        <Text label="Case name / cause title" id="case_name" reg={form.register("case_name")} err={form.formState.errors.case_name?.message} placeholder="e.g. Aurelia Ventures Pvt Ltd v. Stellar Holdings LLP" />
        <SelectF label="Case type" id="case_type" name="case_type" control={form.control} options={C.case_types} />
        <Text label="Court or forum" id="court_or_forum" reg={form.register("court_or_forum")} err={form.formState.errors.court_or_forum?.message} placeholder="e.g. Bombay High Court — Commercial Division" />
        <SelectF label="Jurisdiction" id="jurisdiction" name="jurisdiction" control={form.control} options={C.indian_jurisdictions} />
        <Text label="Client name" id="client_name" reg={form.register("client_name")} err={form.formState.errors.client_name?.message} />
        <SelectF label="Your role in this case" id="your_role_in_case" name="your_role_in_case" control={form.control} options={C.roles_in_case} />
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="party_names">All party names (one per line or comma-separated)</Label>
          <Textarea id="party_names" rows={3} {...form.register("party_names")} />
          {form.formState.errors.party_names && (
            <p className="text-xs text-danger">{form.formState.errors.party_names.message}</p>
          )}
        </div>
        <Text label="Opposing party (or parties)" id="opposing_party_name" reg={form.register("opposing_party_name")} err={form.formState.errors.opposing_party_name?.message} />
        <Text label="Filing date" id="filing_date" type="date" reg={form.register("filing_date")} err={form.formState.errors.filing_date?.message} />
        <Text label="Next hearing date (optional)" id="next_hearing_date" type="date" reg={form.register("next_hearing_date")} err={form.formState.errors.next_hearing_date?.message} />
        <SelectF label="Urgency" id="urgency_level" name="urgency_level" control={form.control} options={C.urgency_levels} />
        <SelectF label="Confidentiality" id="confidentiality_level" name="confidentiality_level" control={form.control} options={C.confidentiality_levels} />
        <SelectF label="Status" id="case_status" name="case_status" control={form.control} options={C.case_statuses} />
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="short_case_summary">Short case summary</Label>
          <Textarea id="short_case_summary" rows={4} placeholder="One paragraph: parties, dispute, prayer." {...form.register("short_case_summary")} />
          {form.formState.errors.short_case_summary && (
            <p className="text-xs text-danger">{form.formState.errors.short_case_summary.message}</p>
          )}
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="internal_notes">Internal notes (optional)</Label>
          <Textarea id="internal_notes" rows={3} placeholder="Strategy notes, witness reminders, pending tasks." {...form.register("internal_notes")} />
        </div>
      </div>

      {form.formState.errors.root?.message && (
        <p className="text-sm text-danger">{form.formState.errors.root.message}</p>
      )}

      <div className="flex items-center justify-end gap-3">
        <Button type="button" variant="ghost" onClick={() => router.back()}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" size="lg" disabled={mutation.isPending}>
          {mutation.isPending && <Spinner />}
          {firstCase ? "Create case and open workspace" : "Create case"}
        </Button>
      </div>
    </form>
  );
}

function Text({
  label,
  id,
  reg,
  err,
  type,
  placeholder,
}: {
  label: string;
  id: string;
  reg: ReturnType<ReturnType<typeof useForm<CaseInput>>["register"]>;
  err?: string;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} placeholder={placeholder} {...reg} />
      {err && <p className="text-xs text-danger">{err}</p>}
    </div>
  );
}

function SelectF({
  label,
  id,
  name,
  control,
  options,
}: {
  label: string;
  id: string;
  name: keyof CaseInput;
  control: ReturnType<typeof useForm<CaseInput>>["control"];
  options: string[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select value={(field.value as string) ?? ""} onValueChange={field.onChange}>
            <SelectTrigger id={id}>
              <SelectValue placeholder="Choose…" />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </div>
  );
}
