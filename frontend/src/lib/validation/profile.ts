import { z } from "zod";

export const profileSchema = z.object({
  full_name: z.string().min(2, "Required").max(160),
  display_name: z.string().min(1, "Required").max(80),
  email: z.string().email(),
  firm_name: z.string().min(2, "Required").max(160),
  practice_area: z.string().min(2),
  years_of_experience: z.coerce.number().int().min(0).max(70),
  jurisdiction_focus: z.string().min(2),
  city: z.string().min(2, "Required").max(80),
  preferred_languages: z.array(z.string()).min(1, "Select at least one language."),
  bar_registration_id: z.string().max(80).optional().nullable(),
  phone: z.string().max(40).optional().nullable(),
  default_workspace_theme: z.string().min(2),
});

export type ProfileInput = z.infer<typeof profileSchema>;
