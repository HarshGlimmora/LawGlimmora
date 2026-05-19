import { Eyebrow } from "@/components/atoms/eyebrow";
import { ProfileForm } from "@/features/profile/profile-form";

export const metadata = { title: "Counsel profile · Glimmora Lawyer" };

export default function ProfileSetupPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="space-y-3 animate-fade-in">
        <Eyebrow>Step 1 · Counsel profile</Eyebrow>
        <h1>Set up your counsel profile</h1>
        <p className="max-w-2xl text-[0.95rem] leading-relaxed text-ink-soft">
          This profile is your workspace identity. It shapes how your cases,
          hearings, and AI outputs are framed throughout Glimmora Lawyer.
        </p>
      </div>
      <div className="surface mt-8 p-7">
        <ProfileForm />
      </div>
    </div>
  );
}
