"use client";

/**
 * Last-resort error boundary. Runs only when the root layout itself
 * crashes. Must include <html> and <body> because it replaces the
 * whole document.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          backgroundColor: "#F6F2E9",
          color: "#0F1419",
          fontFamily: '"IBM Plex Sans", "Helvetica Neue", Arial, sans-serif',
        }}
      >
        <main
          style={{
            maxWidth: 720,
            margin: "0 auto",
            padding: "96px 24px",
          }}
        >
          <div
            style={{
              fontFamily: '"IBM Plex Mono", Menlo, monospace',
              fontSize: 12,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#7A4A1F",
            }}
          >
            Glimmora Lawyer · Fatal error
          </div>
          <h1
            style={{
              marginTop: 16,
              fontFamily: '"Fraunces", "Cormorant Garamond", Georgia, serif',
              fontSize: "2rem",
              fontWeight: 500,
              lineHeight: 1.1,
            }}
          >
            The workspace failed to load.
          </h1>
          <p style={{ marginTop: 16, color: "#22303C", lineHeight: 1.55 }}>
            We hit an unrecoverable error before the workspace could mount.
            Try refreshing the page. If this keeps happening, share the trace
            id with the team.
          </p>
          {error.digest && (
            <code
              style={{
                display: "inline-block",
                marginTop: 16,
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid #E4DDCC",
                background: "#FFFFFF",
                fontFamily: '"IBM Plex Mono", Menlo, monospace',
                fontSize: 12,
                color: "#6B7280",
              }}
            >
              trace: {error.digest}
            </code>
          )}
          <div style={{ marginTop: 24 }}>
            <button
              onClick={() => reset()}
              style={{
                appearance: "none",
                cursor: "pointer",
                border: 0,
                borderRadius: 8,
                padding: "10px 18px",
                background: "#7A4A1F",
                color: "white",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
