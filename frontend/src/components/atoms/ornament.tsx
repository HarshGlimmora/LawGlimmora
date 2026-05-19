/**
 * Editorial divider — a hairline + serif glyph. Used between sections in
 * marketing/auth surfaces to break the page without resorting to plain hr.
 */
export function Ornament({ glyph = "§" }: { glyph?: string }) {
  return (
    <div className="my-8 flex items-center justify-center gap-4" aria-hidden>
      <span className="h-px w-16 bg-rule" />
      <span className="font-display text-base text-accent">{glyph}</span>
      <span className="h-px w-16 bg-rule" />
    </div>
  );
}
