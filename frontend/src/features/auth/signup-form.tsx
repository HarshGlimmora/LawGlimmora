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
import { signupSchema, type SignupInput } from "@/lib/validation/auth";

export function SignupForm({ onSignedUp }: { onSignedUp?: () => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const form = useForm<SignupInput>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: "", password: "", password_confirm: "" },
  });

  const mutation = useMutation({
    mutationFn: authEndpoints.signup,
    onSuccess: (user) => {
      qc.setQueryData(qk.me, user);
      onSignedUp?.();
      router.replace("/profile-setup");
    },
    onError: (err) => {
      form.setError("root", {
        message: err instanceof ApiError ? err.message : "Signup failed.",
      });
    },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
      noValidate
    >
      <div className="space-y-1.5">
        <Label htmlFor="signup-email">Email</Label>
        <Input
          id="signup-email"
          type="email"
          autoComplete="email"
          placeholder="you@chambers.law"
          {...form.register("email")}
        />
        {form.formState.errors.email && (
          <p className="text-xs text-danger">{form.formState.errors.email.message}</p>
        )}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="signup-pwd">Password</Label>
        <Input
          id="signup-pwd"
          type="password"
          autoComplete="new-password"
          {...form.register("password")}
        />
        <p className="text-xs text-ink-mute">Minimum 8 characters.</p>
        {form.formState.errors.password && (
          <p className="text-xs text-danger">{form.formState.errors.password.message}</p>
        )}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="signup-pwd2">Confirm password</Label>
        <Input
          id="signup-pwd2"
          type="password"
          autoComplete="new-password"
          {...form.register("password_confirm")}
        />
        {form.formState.errors.password_confirm && (
          <p className="text-xs text-danger">
            {form.formState.errors.password_confirm.message}
          </p>
        )}
      </div>
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
        Create account
      </Button>
    </form>
  );
}
