import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import { api, money, moneyCompact, pct } from "../api";
import { Kpi, FamilyDonut, FamilyLegend } from "./shared.jsx";

export default function PortfolioDashboard() {
  const [p, setP] = useState(null);
  const [uplift, setUplift] = useState(null);
  const [members, setMembers] = useState([]);

  useEffect(() => {
    api.portfolio().then(setP);
    api.uplift().then(setUplift);
    api.members({ limit: 12 }).then((d) => setMembers(d.items));
  }, []);

  if (!p) return <div className="loading">Loading portfolio analytics…</div>;

  const productData = p.by_product.map((d) => ({
    name: d.product.replace("Membership Rewards Card (MRCC)", "MRCC"),
    Unclaimed: d.unclaimed,
    Realized: d.realized,
    utilization: d.utilization,
  }));
  const distData = Object.entries(p.utilization_distribution).map(([k, v]) => ({ name: k, members: v }));
  const fi = uplift?.model?.feature_importance || {};
  const fiData = Object.entries(fi)
    .map(([k, v]) => ({ name: k, v }))
    .sort((a, b) => b.v - a.v)
    .slice(0, 7);

  return (
    <div>
      <div className="grid cols-4">
        <Kpi label="Unclaimed value (portfolio)" value={moneyCompact(p.total_unclaimed)} accent big
             foot={`across ${p.n_members} card members`} />
        <Kpi label="Avg unclaimed / member" value={moneyCompact(p.avg_unclaimed_per_member)}
             foot="annualized opportunity" />
        <Kpi label="Portfolio utilization" value={pct(p.portfolio_utilization)}
             foot={`${moneyCompact(p.total_realized)} of ${moneyCompact(p.total_entitlement)} realized`} />
        <Kpi label="Reward points value at stake" value={moneyCompact(p.points_value_locked)}
             foot="MR balances valued at transfer rate" />
      </div>

      <div className="grid cols-2" style={{ marginTop: 18, gridTemplateColumns: "1fr 1.3fr" }}>
        <div className="card">
          <h3>Unclaimed value by family</h3>
          <div className="sub">Where the leakage concentrates</div>
          <FamilyDonut byFamily={p.unclaimed_by_family} total={p.total_unclaimed} />
          <FamilyLegend byFamily={p.unclaimed_by_family} />
        </div>

        <div className="card">
          <h3>Realized vs. unclaimed by product</h3>
          <div className="sub">Annualized benefit value (₹)</div>
          <div style={{ width: "100%", height: 230 }}>
            <ResponsiveContainer>
              <BarChart data={productData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => moneyCompact(v)} />
                <Bar dataKey="Realized" stackId="a" fill="#9fc4ea" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Unclaimed" stackId="a" fill="#006fcf" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3>Utilization distribution</h3>
          <div className="sub">How many members fall in each utilization band</div>
          <div style={{ width: "100%", height: 210 }}>
            <ResponsiveContainer>
              <BarChart data={distData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="members" radius={[6, 6, 0, 0]}>
                  {distData.map((d, i) => (
                    <Cell key={i} fill={["#d64545", "#e0a02a", "#5aa9e6", "#1e9e6a"][i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3>Nudge targeting uplift</h3>
          <div className="sub">
            Model-targeted nudging vs. a random/blanket campaign of the same size
            ({uplift ? uplift.nudges_sent : "…"} nudges)
          </div>
          {uplift && (
            <>
              <div className="grid cols-2" style={{ marginTop: 6 }}>
                <div>
                  <div className="uplift-num good">{uplift.recovered_value_uplift_x}×</div>
                  <div className="foot">more recovered value vs. random targeting</div>
                </div>
                <div>
                  <div className="uplift-num">{uplift.conversion_uplift_x}×</div>
                  <div className="foot">higher conversion rate on nudges sent</div>
                </div>
              </div>
              <div className="metarow" style={{ display: "flex", gap: 18, marginTop: 16, flexWrap: "wrap", fontSize: 12.5, color: "var(--muted)" }}>
                <span>Targeted recovered · <b>{moneyCompact(uplift.targeted.expected_recovered)}</b></span>
                <span>Random recovered · <b>{moneyCompact(uplift.random_baseline.expected_recovered)}</b></span>
              </div>
              <p className="footnote">
                Propensity model: <b>{uplift.model.kind}</b> · AUC{" "}
                <b>{uplift.model.metrics.auc ?? "—"}</b> · top-decile lift{" "}
                <b>{uplift.model.metrics.top_decile_lift ?? "—"}×</b> · base conversion{" "}
                <b>{pct(uplift.model.metrics.base_conversion_rate, 1)}</b>
              </p>
            </>
          )}
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 18, gridTemplateColumns: "1.3fr 1fr" }}>
        <div className="card">
          <h3>Highest-opportunity members</h3>
          <div className="sub">Prioritized for proactive outreach</div>
          <table className="leaderboard">
            <thead>
              <tr>
                <th>Member</th>
                <th>Product</th>
                <th>Utilization</th>
                <th style={{ textAlign: "right" }}>Unclaimed</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.member_id}>
                  <td>{m.name}</td>
                  <td>{m.product}</td>
                  <td>
                    <span className="mini-bar">
                      <span style={{ width: pct(m.utilization) }} />
                    </span>{" "}
                    {pct(m.utilization)}
                  </td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>{moneyCompact(m.total_unclaimed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>What drives engagement</h3>
          <div className="sub">Top propensity-model feature importances</div>
          <div style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer>
              <BarChart layout="vertical" data={fiData} margin={{ top: 4, right: 16, left: 30, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                <Tooltip formatter={(v) => v.toFixed(3)} />
                <Bar dataKey="v" fill="#7b5cff" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <p className="footnote" style={{ marginTop: 18 }}>
        Reference date {p.reference_date}. All figures over a trailing 12-month transaction window
        (a proxy for the cardmembership year). Unclaimed value spans statement credits, lounge access,
        protection coverage, missed Amex Offers and near-miss milestone rewards. Protection value is a
        probabilistic expected-recoverable figure (coverage rate × eligible protected spend). Membership
        Rewards balances are shown separately, valued across a redemption range.
      </p>
    </div>
  );
}
