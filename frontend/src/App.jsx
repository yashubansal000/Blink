import { useState, useEffect } from "react";
import { shortenUrl, fetchLinks } from "./api";

function App() {
  const [longUrl, setLongUrl] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(false);

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await shortenUrl(longUrl);
      setResult(data);
      setLongUrl("");
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;