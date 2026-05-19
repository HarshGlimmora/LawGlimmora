import Link from "next/link";

import { Eyebrow } from "@/components/atoms/eyebrow";
import { SignupForm } from "@/features/auth/signup-form";

export const metadata = { title: "Create account · Glimmora Lawyer" };

export default function SignupPage() {
  return (
    <div className="mx-auto max-w-md">
      <Eyebrow>Counsel access</Eyebrow>
      <h1 className="mt-3">Create your account</h1>
      <p className="mt-2 text-sm text-ink-mute">
        We&apos;ll set up your profile and first case in the next two steps.
      </p>
      <div className="surface mt-6 p-7">
        <SignupForm />
      </div>
      <p className="mt-6 text-sm text-ink-mute">
        Already registered?{" "}
        <Link href="/login" className="subtle-link">
          Sign in instead.
        </Link>
      </p>
    </div>
  );
}
