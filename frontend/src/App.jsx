import { useState, useEffect } from "react";
import { shortenUrl, fetchLinks, reportLink } from "./api";
import { supabase } from "./supabaseClient";
import Auth from "./Auth";

function App() {
  const [longUrl, setLongUrl] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(false);

  const [expiresAt, setExpiresAt] = useState("");
  const [customAlias, setCustomAlias] = useState("");
  
  const [session, setSession] = useState(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  
  const [reportingCode, setReportingCode] = useState(null);
  const [reportReason, setReportReason] = useState("");
  const [reportStatus, setReportStatus] = useState("");

  const loadLinks = async (currentSession) => {
    try {
      const token = currentSession?.access_token || null;
      const data = await fetchLinks(token); // fixed: token now actually passed
      setLinks(data);
    } catch (err) {
      console.error(err);
    }
  };


  const submitReport = async (shortCode) => {
    if (!reportReason.trim()) {
      setReportStatus("Please enter a reason.");
      return;
    }

    try {
      const data = await reportLink(shortCode, reportReason);

      setReportStatus(
        data.auto_disabled
          ? "Reported. This link has now been disabled."
          : `Reported. (${data.report_count} report(s) so far)`
      );

      setReportReason("");
      setReportingCode(null);

      await loadLinks(session);
    } catch (err) {
      setReportStatus(err.message);
    }
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setSessionLoaded(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  // Re-fetch links whenever session actually changes (login, logout, or the
  // initial async resolve). The fetch is inlined here (rather than calling
  // loadLinks directly) with an `ignore` guard, per React's recommended
  // pattern for data-fetching effects -- avoids acting on a stale response
  // if session changes again before this fetch resolves.
  useEffect(() => {
    if (!sessionLoaded) return;
    let ignore = false;
    const token = session?.access_token || null;

    (async () => {
      try {
        const data = await fetchLinks(token);
        if (!ignore) setLinks(data);
      } catch (err) {
        if (!ignore) console.error(err);
      }
    })();

    return () => {
      ignore = true;
    };
  }, [session, sessionLoaded]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const token = session?.access_token || null;
      const data = await shortenUrl(longUrl, expiresAt || null, customAlias || null, token);
      setResult(data);
      setLongUrl("");
      setExpiresAt("");
      setCustomAlias("");
      await loadLinks(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 600, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>URL Shortener</h1>

      {session ? (
        <p>
          Logged in as {session.user.email}{" "}
          <button onClick={() => supabase.auth.signOut()}>Log out</button>
        </p>
      ) : (
        <Auth onAuthed={() => {}} />
      )}

      <form onSubmit={handleSubmit}>
        <input
          type="url"
          required
          placeholder="https://example.com/long/path"
          value={longUrl}
          onChange={(e) => setLongUrl(e.target.value)}
          style={{ width: "70%", padding: 8 }}
        />
        <button type="submit" disabled={loading} style={{ padding: 8, marginLeft: 8 }}>
          {loading ? "Shortening..." : "Shorten"}
        </button>

        <div style={{ marginTop: 8 }}>
          <label>
            Expires at (optional):{" "}
            <input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
          </label>
        </div>

        <div style={{ marginTop: 8 }}>
          <label>
            Custom alias (optional):{" "}
            <input type="text" placeholder="my-link" value={customAlias} onChange={(e) => setCustomAlias(e.target.value)} />
          </label>
        </div>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {reportStatus && (
        <p style={{ color: "green" }}>{reportStatus}</p>
      )}

      {result && (
        <p>
          Short URL:{" "}
          <a href={result.short_url} target="_blank" rel="noreferrer">
            {result.short_url}
          </a>
        </p>
      )}

      <h2>Recent Links</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Code</th>
            <th style={{ textAlign: "left" }}>Long URL</th>
            <th style={{ textAlign: "left" }}>Clicks</th>
            <th style={{ textAlign: "left" }}>Status</th>
            <th style={{ textAlign: "left" }}>Reports</th>
            <th style={{ textAlign: "left" }}>Report</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => {
            const isExpired = link.expires_at && new Date(link.expires_at) < new Date();
            let statusLabel;
            let statusColor;
            if (!link.is_active) {
              statusLabel = "Disabled";
              statusColor = "#b91c1c";
            } else if (isExpired) {
              statusLabel = "Expired";
              statusColor = "#b45309";
            } else if (link.expires_at) {
              statusLabel = `Active (expires ${new Date(link.expires_at).toLocaleString()})`;
              statusColor = "#15803d";
            } else {
              statusLabel = "Active (never expires)";
              statusColor = "#15803d";
            }

            return (
              <tr key={link.short_code}>
                <td>{link.short_code}</td>
                <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {link.long_url}
                </td>
                <td>{link.click_count}</td>
                <td style={{ color: statusColor, fontWeight: 500 }}>{statusLabel}</td>
                <td>{link.report_count}</td>
                <td>
                  {reportingCode === link.short_code ? (
                    <div style={{ display: "flex", gap: 4 }}>
                      <input
                        type="text"
                        placeholder="Reason"
                        value={reportReason}
                        onChange={(e) => setReportReason(e.target.value)}
                        style={{ width: 100 }}
                      />
                      <button onClick={() => submitReport(link.short_code)}>Send</button>
                      <button onClick={() => { setReportingCode(null); setReportReason(""); }}>Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => setReportingCode(link.short_code)}>Report</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default App;