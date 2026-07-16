import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { setToken } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function AuthCallback() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash || "";
    const m = hash.match(/token=([^&]+)/);
    if (!m) { nav("/login", { replace: true }); return; }
    const token = decodeURIComponent(m[1]);

    (async () => {
      setToken(token);
      window.history.replaceState(null, "", "/dashboard");
      await refresh();
      nav("/dashboard", { replace: true });
    })();
  }, [nav, refresh]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="font-mono uppercase tracking-widest text-sm" data-testid="auth-callback">Signing you in…</div>
    </div>
  );
}