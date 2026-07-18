import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API, getToken } from "../lib/api";
import { Award, Download, BookOpen, ArrowRight } from "lucide-react";

function Skeleton({ className = "" }) {
  return <div className={`animate-pulse bg-neutral-200 ${className}`} />;
}

async function downloadCertificate(certificateId, filenameHint) {
  const res = await fetch(`${API}/certificates/${certificateId}/download`, {
    headers: { Authorization: `Bearer ${getToken() || ""}` },
  });
  if (!res.ok) throw new Error("Failed to download certificate");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `certificate-${(filenameHint || "course").toLowerCase().replace(/\s+/g, "-")}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function Certificates() {
  const [certs, setCerts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/my/certificates");
        setCerts(data);
      } catch {
        setError("Couldn't load your certificates. Try refreshing.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleDownload = async (cert) => {
    setDownloadingId(cert.certificate_id);
    try {
      await downloadCertificate(cert.certificate_id, cert.course_title);
    } catch {
      setError("Download failed. Try again.");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <span className="section-tag">Your achievements</span>
      <h1 className="font-display text-5xl font-extrabold tracking-tight mt-4">
        Certificates<span className="text-[#FF2E00]">.</span>
      </h1>
      <p className="mt-2 text-neutral-600 max-w-xl">
        Every course you finish earns you a downloadable certificate. Here's what you've unlocked so far.
      </p>

      {error && (
        <div className="brutal-card p-4 mt-6 border-[#FF2E00] text-sm font-mono">{error}</div>
      )}

      {loading ? (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-10">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-48" />)}
        </div>
      ) : !certs?.length ? (
        <div className="brutal-card p-10 text-center border-dashed mt-10">
          <Award size={32} className="mx-auto text-neutral-300 mb-3" />
          <div className="font-mono uppercase tracking-widest text-sm text-neutral-400">
            No certificates yet — complete a course to earn one.
          </div>
          <Link to="/courses" className="brutal-btn brutal-btn--red mt-4 inline-flex text-sm">
            Browse courses <ArrowRight size={14} />
          </Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-10">
          {certs.map((cert) => (
            <div key={cert.certificate_id} className="brutal-card p-5 flex flex-col gap-3" data-testid={`certificate-${cert.course_id}`}>
              <div className="w-10 h-10 border-2 border-black flex items-center justify-center" style={{ background: "#FFE78522" }}>
                <Award size={18} />
              </div>
              <div className="font-display text-xl font-bold leading-tight">{cert.course_title}</div>
              <div className="font-mono text-xs text-neutral-400 uppercase tracking-widest">
                Issued {new Date(cert.issued_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
              </div>
              <button
                onClick={() => handleDownload(cert)}
                disabled={downloadingId === cert.certificate_id}
                className="brutal-btn brutal-btn--red text-xs mt-auto justify-center"
              >
                <Download size={13} />
                {downloadingId === cert.certificate_id ? "Preparing…" : "Download PDF"}
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="brutal-card p-6 mt-10 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <BookOpen size={20} />
          <div className="font-mono text-sm uppercase tracking-widest text-neutral-500">
            Finish an in-progress course to unlock its certificate
          </div>
        </div>
        <Link to="/dashboard" className="brutal-btn text-xs">
          Go to dashboard <ArrowRight size={13} />
        </Link>
      </div>
    </div>
  );
}