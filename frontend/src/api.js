const API_BASE = import.meta.env.VITE_API_BASE_URL;

export async function shortenUrl(longUrl, expiresAt, customAlias, token) {
    const body = { long_url: longUrl };
    if (expiresAt) {
        body.expires_at = new Date(expiresAt).toISOString();
    }
    if (customAlias) {
        body.custom_alias = customAlias; // fixed: backend expects snake_case
    }

    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/shorten`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to shorten URL");
    }
    return res.json();
}

export async function fetchLinks(token) {
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    // fixed: headers were built but never actually passed into fetch()
    const res = await fetch(`${API_BASE}/api/links`, { headers });
    if (!res.ok) throw new Error("Failed to fetch links");
    return res.json();
}

export async function reportLink(shortCode, reason) {
    const res = await fetch(`${API_BASE}/api/links/${shortCode}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to report link");
    }
    return res.json();
}