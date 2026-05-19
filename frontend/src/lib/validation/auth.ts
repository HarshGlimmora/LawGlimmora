import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email."),
  password: z.string().min(1, "Password is required."),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const signupSchema = z
  .object({
    email: z.string().email("Enter a valid email."),
    password: z.string().min(8, "Minimum 8 characters."),
    password_confirm: z.string().min(8, "Minimum 8 characters."),
  })
  .refine((v) => v.password === v.password_confirm, {
    path: ["password_confirm"],
    message: "Passwords do not match.",
  });
export type SignupInput = z.infer<typeof signupSchema>;
