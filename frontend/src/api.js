const BASE = "/api";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => get("/health"),
  meta: () => get("/meta"),
  catalog: () => get("/catalog"),
  members: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return get(`/members${q ? `?${q}` : ""}`);
  },
  memberSummary: (id) => get(`/members/${id}/summary`),
  memberNudges: (id, topK = 6) => get(`/members/${id}/nudges?top_k=${topK}`),
  portfolio: () => get("/portfolio"),
  uplift: () => get("/portfolio/uplift"),
};

// Indian Rupee formatting (e.g. ₹1,23,456)
export const money = (n, digits = 0) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(n ?? 0);

// compact for large portfolio figures (₹1.2 Cr / ₹3.4 L)
export const moneyCompact = (n) => {
  const v = n ?? 0;
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return money(v);
};

export const pct = (n, digits = 0) => `${((n ?? 0) * 100).toFixed(digits)}%`;
