import { Info } from "lucide-react";

export function HelpLink({
  onClick,
  children,
}: {
  onClick: () => void;
  children: string;
}) {
  return (
    <button className="help-link" type="button" onClick={onClick}>
      <Info size={12} strokeWidth={1.6} />
      <span>{children}</span>
    </button>
  );
}
