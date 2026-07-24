type Props = {
  className?: string;
  compact?: boolean;
};

/** Space Grotesk wordmark with first letter reversed out of an ink block. */
export function Wordmark({ className = "", compact = false }: Props) {
  return (
    <span
      className={`wordmark inline-flex items-baseline ${compact ? "text-xl tracking-[-0.04em]" : ""} ${className}`}
      aria-label="Bizfluence"
    >
      <span className="wordmark-block">B</span>
      <span>izfluence</span>
    </span>
  );
}
