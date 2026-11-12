import { Info } from "lucide-react";

export function HelpTip({
  label,
  definition,
  onOpen,
}: {
  label: string;
  definition: string;
  onOpen: () => void;
}) {
  return (
    <span className="help-tip" tabIndex={0} aria-label={`${label}: ${definition}`}>
      <Info size={11} strokeWidth={1.6} />
      <span className="help-tip-panel" role="tooltip">
        <strong>{label}</strong>
        <span>{definition}</span>
        <button type="button" onClick={onOpen}>
          Read the full article
        </button>
      </span>
    </span>
  );
}
