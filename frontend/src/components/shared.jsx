import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { moneyCompact } from "../api";

export const FAMILY_COLOR = {
  credit: "#006fcf",
  lounge: "#7b5cff",
  protection: "#1e9e6a",
  offer: "#e0672a",
  milestone: "#c8102e",
  points: "#b8860b",
};
export const FAMILY_LABEL = {
  credit: "Statement credits",
  lounge: "Lounge access",
  protection: "Protection coverage",
  offer: "Amex Offers",
  milestone: "Milestone rewards",
  points: "Reward points",
};

export function Kpi({ label, value, foot, accent, big }) {
  return (
    <div className="card kpi">
      <span className="label">{label}</span>
      <span className={`value ${big ? "big" : ""} ${accent ? "accent" : ""}`}>{value}</span>
      {foot && <span className="foot">{foot}</span>}
    </div>
  );
}

export function FamilyDonut({ byFamily, total, centerLabel = "unclaimed" }) {
  const data = Object.entries(byFamily || {})
    .map(([k, v]) => ({ name: k, value: v }))
    .filter((d) => d.value > 0);
  if (data.length === 0) data.push({ name: "credit", value: 1 });
  return (
    <div style={{ position: "relative", width: "100%", height: 190 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={62} outerRadius={88} paddingAngle={2} stroke="none">
            {data.map((d) => (
              <Cell key={d.name} fill={FAMILY_COLOR[d.name] || "#ccc"} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 850, letterSpacing: "-1px" }}>{moneyCompact(total)}</div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
            {centerLabel}
          </div>
        </div>
      </div>
    </div>
  );
}

export function FamilyLegend({ byFamily }) {
  const keys = Object.keys(FAMILY_LABEL).filter((k) => !byFamily || byFamily[k] !== undefined);
  return (
    <div className="legend">
      {keys.map((k) => (
        <span key={k}>
          <i className="dot" style={{ background: FAMILY_COLOR[k] }} />
          {FAMILY_LABEL[k]}
          {byFamily ? ` · ${moneyCompact(byFamily[k] || 0)}` : ""}
        </span>
      ))}
    </div>
  );
}
