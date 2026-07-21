const API_BASE = import.meta.env.VITE_API_BASE_URL;

export async function shortenUrl(longUrl) {
    const res = await fetch(`${API_BASE}/api/shorten`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ long_url: longUrl }),
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