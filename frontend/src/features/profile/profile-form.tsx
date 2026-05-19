"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/ui/multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/feedback/spinner";
import { useConstants } from "@/hooks/use-constants";
import { useSession } from "@/hooks/use-session";
import { ApiError } from "@/lib/api/client";
import { profileEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { languagesToArray } from "@/lib/utils";
import {
  profileSchema,
  type ProfileInput,
} from "@/lib/validation/profile";

interface ProfileFormProps {
  redirectOnSave?: string;
  submitLabel?: string;
}

export function ProfileForm({
  redirectOnSave = "/dashboard",
  submitLabel = "Save profile and continue",
}: ProfileFormProps) {
  const router = useRouter();
  const qc = useQueryClient();
  const session = useSession();
  const constants = useConstants();
  const existing = useQuery({ queryKey: qk.profile, queryFn: profileEndpoints.get });

  const form = useForm<ProfileInput>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: "",
      display_name: "",
      email: session.data?.email ?? "",
      firm_name: "",
      practice_area: "",
      years_of_experience: 0,
      jurisdiction_focus: "",
      city: "",
      preferred_languages: ["English"],
      bar_registration_id: "",
      phone: "",
      default_workspace_theme: "Parchment (light)",
    },
  });

  useEffect(() => {
    if (!existing.data) return;
    form.reset({
      full_name: existing.data.full_name,
      display_name: existing.data.display_name,
      email: session.data?.email ?? "",
      firm_name: existing.data.firm_name,
      practice_area: existing.data.practice_area,
      years_of_experience: existing.data.years_of_experience,
      jurisdiction_focus: existing.data.jurisdiction_focus,
      city: existing.data.city,
      preferred_languages: languagesToArray(existing.data.preferred_languages),
      bar_registration_id: existing.data.bar_registration_id ?? "",
      phone: existing.data.phone ?? "",
      default_workspace_theme: existing.data.default_workspace_theme,
    });
  }, [existing.data, session.data?.email, form]);

  const mutation = useMutation({
    mutationFn: profileEndpoints.save,
    onSuccess: (saved) => {
      qc.setQueryData(qk.profile, saved);
      qc.invalidateQueries({ queryKey: qk.me });
      router.replace(redirectOnSave);
    },
    onError: (err) => {
      form.setError("root", {
        message: err instanceof ApiError ? err.message : "Save failed.",
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
        <FieldText
          id="full_name"
          label="Full name (as on Bar roll)"
          register={form.register("full_name")}
          error={form.formState.errors.full_name?.message}
        />
        <FieldText
          id="display_name"
          label="Display name (shown in workspace)"
          register={form.register("display_name")}
          error={form.formState.errors.display_name?.message}
        />
        <FieldText
          id="email"
          label="Email"
          disabled
          register={form.register("email")}
          error={form.formState.errors.email?.message}
        />
        <FieldText
          id="firm_name"
          label="Firm / chambers"
          register={form.register("firm_name")}
          error={form.formState.errors.firm_name?.message}
        />
        <FieldSelect
          id="practice_area"
          label="Primary practice area"
          control={form.control as never}
          name="practice_area"
          options={C.practice_areas}
        />
        <div className="space-y-1.5">
          <Label htmlFor="years_of_experience">Years of experience</Label>
          <Input
            id="years_of_experience"
            type="number"
            min={0}
            max={70}
            {...form.register("years_of_experience", { valueAsNumber: true })}
          />
          {form.formState.errors.years_of_experience && (
            <p className="text-xs text-danger">
              {form.formState.errors.years_of_experience.message}
            </p>
          )}
        </div>
        <FieldSelect
          id="jurisdiction_focus"
          label="Jurisdiction focus"
          control={form.control as never}
          name="jurisdiction_focus"
          options={C.indian_jurisdictions}
        />
        <FieldText
          id="city"
          label="City"
          register={form.register("city")}
          error={form.formState.errors.city?.message}
        />
        <div className="space-y-1.5 md:col-span-2">
          <Label>Preferred languages</Label>
          <Controller
            control={form.control}
            name="preferred_languages"
            render={({ field }) => (
              <MultiSelect
                options={C.languages}
                value={field.value}
                onChange={field.onChange}
                placeholder="Select languages…"
              />
            )}
          />
          {form.formState.errors.preferred_languages && (
            <p className="text-xs text-danger">
              {form.formState.errors.preferred_languages.message}
            </p>
          )}
        </div>
        <FieldText
          id="bar_registration_id"
          label="Bar registration ID (optional)"
          register={form.register("bar_registration_id")}
        />
        <FieldText
          id="phone"
          label="Phone (optional)"
          register={form.register("phone")}
        />
        <FieldSelect
          id="default_workspace_theme"
          label="Default workspace theme"
          control={form.control as never}
          name="default_workspace_theme"
          options={C.workspace_themes}
        />
      </div>

      {form.formState.errors.root?.message && (
        <p className="text-sm text-danger">{form.formState.errors.root.message}</p>
      )}

      <div className="flex justify-end">
        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={mutation.isPending}
        >
          {mutation.isPending && <Spinner />}
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

function FieldText({
  id,
  label,
  register,
  error,
  disabled,
}: {
  id: string;
  label: string;
  register: ReturnType<ReturnType<typeof useForm<ProfileInput>>["register"]>;
  error?: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} disabled={disabled} {...register} />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

function FieldSelect({
  id,
  label,
  control,
  name,
  options,
}: {
  id: string;
  label: string;
  control: never;
  name: keyof ProfileInput;
  options: string[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select
            value={(field.value as string) ?? ""}
            onValueChange={field.onChange}
          >
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
