import { redirect } from "next/navigation";
import { cookies } from "next/headers";

/**
 * Root → routes by session presence. Server-side check on the cookie
 * keeps the first paint correct (no flash of unauthenticated state).
 */
export default function RootPage() {
  const hasSession = cookies().has("glimmora_session");
  redirect(hasSession ? "/dashboard" : "/login");
}
