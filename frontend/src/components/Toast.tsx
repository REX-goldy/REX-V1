import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

type Tone = "success" | "error";

interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

interface ToastContextValue {
  notify: (message: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const notify = useCallback((message: string, tone: Tone = "success") => {
    const id = nextId++;
    setItems((current) => [...current, { id, message, tone }]);
  }, []);

  useEffect(() => {
    if (!items.length) return;
    const timer = window.setTimeout(() => {
      setItems((current) => current.slice(1));
    }, 5200);
    return () => window.clearTimeout(timer);
  }, [items]);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-host" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={`toast ${item.tone === "error" ? "error" : ""}`}>
            {item.tone === "error" ? <AlertTriangle /> : <CheckCircle2 />}
            <span>{item.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
