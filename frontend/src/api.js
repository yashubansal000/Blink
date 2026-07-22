const API_BASE = import.meta.env.VITE_API_BASE_URL;

export async function shortenUrl(longUrl, expiresAt, customAlias, token) {
    const body = { long_url: longUrl };
    if (expiresAt){
        body.expires_at = new Date(expiresAt).toISOString();
    }
    if (customAlias){
        body.customAlias = customAlias;
    }

    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    
    const res = await fetch(`${API_BASE}/api/shorten`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
    });
    if(!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to shorten URL");
    }
    return res.json();
}

export async function fetchLinks() {
    const res = await fetch(`${API_BASE}/api/links`);
    if(!res.ok) throw new Error("Failed to fetch links");
    return res.json();
}