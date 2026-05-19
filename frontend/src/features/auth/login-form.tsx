"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/feedback/spinner";
import { ApiError } from "@/lib/api/client";
import { authEndpoints } from "@/lib/api/endpoints";
import { qk } from "@/lib/api/query-keys";
import { log } from "@/lib/logger";
import { loginSchema, type LoginInput } from "@/lib/validation/auth";

export function LoginForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const form = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: authEndpoints.login,
    onSuccess: (user) => {
      log.info("auth", "login ok", { uid: user.id });
      qc.setQueryData(qk.me, user);
      router.replace(user.has_profile ? "/dashboard" : "/profile-setup");
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : "Login failed.";
      form.setError("root", { message: msg });
    },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
      noValidate
    >
      <Field
        id="login-email"
        label="Registered email"
        error={form.formState.errors.email?.message}
      >
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          placeholder="counsel@chambers.law"
          {...form.register("email")}
        />
      </Field>
      <Field
        id="login-password"
        label="Password"
        error={form.formState.errors.password?.message}
      >
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          {...form.register("password")}
        />
      </Field>
      {form.formState.errors.root?.message && (
        <p className="text-sm text-danger">{form.formState.errors.root.message}</p>
      )}
      <Button
        type="submit"
        variant="primary"
        size="lg"
        className="w-full"
        disabled={mutation.isPending}
      >
        {mutation.isPending && <Spinner />}
        Sign in
      </Button>
    </form>
  );
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
