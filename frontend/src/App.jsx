import { useState, useEffect } from "react";
import { shortenUrl, fetchLinks } from "./api";
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

  const loadLinks = async () => {
    try {
      const data = await fetchLinks();
      setLinks(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    let ignore = false;

    async function fetchInitialLinks() {
      try {
        const data = await fetchLinks();
        if (!ignore) {
          setLinks(data);
        }
      } catch (err) {
        if (!ignore) {
          console.error(err);
        }
      }
    }
    fetchInitialLinks();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const token = session?.access_token || null;
      const data = await shortenUrl(
        longUrl, 
        expiresAt || null,
        customAlias || null,
        token
      );
      setResult(data);
      setLongUrl("");
      setExpiresAt("");
      setCustomAlias("");
      await loadLinks();
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
      ): (
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

        <div style={{marginTop: 8}}>
          <label>
            Expires at (optional):{" "}
            <input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)}/>
          </label>
        </div>

        <div style={{ marginTop: 8 }}>
          <label>
            Custom alias (optional):{" "}
            <input type="text" placeholder="my-link" value={customAlias} onChange={(e) => setCustomAlias(e.target.value)}/>
          </label>
        </div>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}

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
            <th style={{ textAlign: "left" }}>Expires</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.short_code}>
              <td>{link.short_code}</td>
              <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                {link.long_url}
              </td>
              <td>{link.click_count}</td>
              <td>{link.expires_at ? new Date(link.expires_at).toLocaleString(): "Never"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;