/**
 * Tiny client logger. Dev-only console output; in prod it's a no-op except for errors.
 * Use for UI events (form submit, route nav, API error) — never for sensitive data.
 */
type Level = "debug" | "info" | "warn" | "error";

const isDev = process.env.NODE_ENV !== "production";

function emit(level: Level, scope: string, msg: string, extra?: unknown) {
  if (!isDev && level !== "error" && level !== "warn") return;
  const tag = `%c[gl:${scope}]`;
  const style =
    level === "error"
      ? "color:#7B1E3A;font-weight:600"
      : level === "warn"
        ? "color:#9A6B12;font-weight:600"
        : "color:#7A4A1F";
  // eslint-disable-next-line no-console
  console[level === "debug" ? "log" : level](tag, style, msg, extra ?? "");
}

export const log = {
  debug: (scope: string, msg: string, extra?: unknown) => emit("debug", scope, msg, extra),
  info: (scope: string, msg: string, extra?: unknown) => emit("info", scope, msg, extra),
  warn: (scope: string, msg: string, extra?: unknown) => emit("warn", scope, msg, extra),
  error: (scope: string, msg: string, extra?: unknown) => emit("error", scope, msg, extra),
};
