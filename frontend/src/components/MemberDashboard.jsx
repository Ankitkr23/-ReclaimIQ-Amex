import { useEffect, useState } from "react";
import { api, money, moneyCompact, pct } from "../api";
import { FamilyDonut, FamilyLegend, FAMILY_COLOR, FAMILY_LABEL } from "./shared.jsx";

export default function MemberDashboard() {
  const [members, setMembers] = useState([]);
  const [selected, setSelected] = useState("");
  const [summary, setSummary] = useState(null);
  const [nudges, setNudges] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.members({ limit: 150 }).then((d) => {
      setMembers(d.items);
      if (d.items.length) setSelected(d.items[0].member_id);
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    Promise.all([api.memberSummary(selected), api.memberNudges(selected, 6)])
      .then(([s, n]) => { setSummary(s); setNudges(n); })
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <div>
      <div className="picker" style={{ marginBottom: 20 }}>
        <span className="hint">Card member</span>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {members.map((m) => (
            <option key={m.member_id} value={m.member_id}>
              {m.name} · {m.product} · {moneyCompact(m.total_unclaimed)} unclaimed
            </option>
          ))}
        </select>
        <span className="hint">Sorted by highest unclaimed value (top 150)</span>
      </div>

      {loading || !summary ? (
        <div className="loading">Loading member analytics…</div>
      ) : (
        <>
          <div className="grid cols-2" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
            <div className="hero">
              <div className="cardface" />
              <div className="eyebrow">{summary.product.name} · value left on the table</div>
              <div className="money">{money(summary.total_unclaimed)}</div>
              <div className="sub">
                {summary.name}, over the last 12 months you captured {pct(summary.utilization)} of your
                benefit entitlements. Here's what's still recoverable — and how to claim it.
              </div>
              <div className="chips">
                <div className="chip"><div className="n">{moneyCompact(summary.total_realized)}</div><div className="l">Value realized</div></div>
                <div className="chip"><div className="n">{pct(summary.utilization)}</div><div className="l">Utilization</div></div>
                <div className="chip"><div className="n">{summary.annual_fee_offset.toFixed(1)}×</div><div className="l">Annual fee offset</div></div>
              </div>
            </div>

            <div className="card">
              <h3>Where the value sits</h3>
              <div className="sub">Unclaimed value by benefit family</div>
              <FamilyDonut byFamily={summary.unclaimed_by_family} total={summary.total_unclaimed} />
              <FamilyLegend byFamily={summary.unclaimed_by_family} />
            </div>
          </div>

          {/* Points value range */}
          <div className="section-title">Your Membership Rewards points</div>
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 26, fontWeight: 850 }}>{summary.points.balance.toLocaleString("en-IN")} pts</div>
                <div className="detail">{summary.points.message}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="detail">Redemption mode: <b>{summary.points.redemption_mode.replace("_", " ")}</b></div>
                <div className="detail">Earned last 12m: {Math.round(summary.points.earned_12m).toLocaleString("en-IN")} pts</div>
              </div>
            </div>
            <div style={{ marginTop: 14 }}>
              <PointsRange value={summary.points.value} />
            </div>
          </div>

          {/* Milestones */}
          {summary.milestones.items.length > 0 && (
            <>
              <div className="section-title">Milestone progress</div>
              <div className="grid cols-3">
                {summary.milestones.items.map((m) => (
                  <MilestoneCard key={m.milestone_id} m={m} />
                ))}
              </div>
            </>
          )}

          {/* Top opportunities (unified across families) */}
          <div className="section-title">Top unclaimed opportunities</div>
          <div className="card">
            {summary.top_opportunities.map((o, i) => (
              <div className="benefit" key={i}>
                <div>
                  <div className="name">
                    {o.name}
                    <span className={`pill ${o.family}`}>{FAMILY_LABEL[o.family] || o.family}</span>
                  </div>
                  <div className="detail">{o.detail}</div>
                </div>
                <div className="right">
                  <div className="gap">{money(o.unclaimed_value)}</div>
                  <div className="detail">recoverable</div>
                </div>
              </div>
            ))}
            {summary.top_opportunities.length === 0 && <div className="detail">Great — no material gaps detected.</div>}
          </div>

          {/* Amex Offers */}
          {(summary.offers.missed.length > 0 || summary.offers.at_risk.length > 0) && (
            <>
              <div className="section-title">Amex Offers</div>
              <div className="grid cols-2">
                {summary.offers.missed.slice(0, 3).map((o) => (
                  <div className="nudge" key={o.offer_id}>
                    <div className="head"><span className="pill offer">missed</span><span className="channel">{o.merchant}</span></div>
                    <div className="headline">Spent {money(o.spend_in_window)} at {o.merchant} — but the offer worth {money(o.reward_value_inr)} was never activated.</div>
                    <div className="action">→ Save offers to your card before you shop.</div>
                  </div>
                ))}
                {summary.offers.at_risk.slice(0, 3).map((o) => (
                  <div className="nudge" key={o.offer_id}>
                    <div className="head"><span className="pill partial">at risk</span><span className="channel">{o.merchant}</span></div>
                    <div className="headline">Activated: spend {money(o.remaining_spend)} more at {o.merchant} by {o.end_date} to earn {money(o.reward_value_inr)}.</div>
                    <div className="action">→ {o.days_left} days left.</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Nudges */}
          <div className="section-title">Personalized nudges · ranked by expected recovered value</div>
          <div className="grid cols-2">
            {nudges?.nudges?.map((n, i) => (
              <div className="nudge" key={i}>
                <div className="head">
                  <span className={`pill ${n.family}`}>{FAMILY_LABEL[n.family] || n.family}</span>
                  <span className="channel">{n.channel_label}</span>
                </div>
                <div className="headline">{n.headline}</div>
                <div className="action">→ {n.action}</div>
                <div className="metarow">
                  <span>Convert prob · <b>{pct(n.convert_probability, 1)}</b></span>
                  <span>Expected recovered · <b>{money(n.expected_recovered_value)}</b></span>
                  <span>Timing · <b>{n.recommended_timing}</b></span>
                </div>
              </div>
            ))}
          </div>
          {nudges && (
            <p className="footnote">
              Total expected recoverable from these nudges: <b>{money(nudges.total_expected_recoverable)}</b>.
              Expected value = rupee gap × model-predicted probability the member converts if nudged.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function PointsRange({ value }) {
  const max = value.airline_premium || 1;
  const seg = [
    { label: "Statement credit", v: value.statement_credit, c: "#b8b8b8" },
    { label: "Hotel transfer", v: value.hotel_transfer, c: "#b8860b" },
    { label: "Airline premium", v: value.airline_premium, c: "#1e9e6a" },
  ];
  return (
    <div>
      {seg.map((s) => (
        <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <div style={{ width: 130, fontSize: 12.5, color: "var(--muted)" }}>{s.label}</div>
          <div className="bar" style={{ flex: 1, gridColumn: "auto", marginTop: 0 }}>
            <span style={{ width: `${(s.v / max) * 100}%`, background: s.c }} />
          </div>
          <div style={{ width: 90, textAlign: "right", fontWeight: 700, fontSize: 13 }}>{moneyCompact(s.v)}</div>
        </div>
      ))}
    </div>
  );
}

function MilestoneCard({ m }) {
  const statusPill = {
    achieved: "on_track", on_track: "on_track", near_miss: "partial", partial: "partial",
    lost_not_enrolled: "unused", locked: "unused", unused: "unused",
  }[m.status] || "partial";
  if (m.cadence === "annual") {
    const progress = Math.min(1, (m.spend || 0) / m.threshold);
    return (
      <div className="card">
        <div className="name" style={{ justifyContent: "space-between", display: "flex" }}>
          <span>{m.name}</span><span className={`pill ${statusPill}`}>{m.status.replace(/_/g, " ")}</span>
        </div>
        <div className="detail" style={{ marginTop: 6 }}>
          {moneyCompact(m.spend)} of {moneyCompact(m.threshold)} · reward {money(m.reward_value)}
        </div>
        <div className="bar" style={{ gridColumn: "auto" }}>
          <span style={{ width: pct(progress), background: FAMILY_COLOR.milestone }} />
        </div>
        {m.status === "near_miss" && (
          <div className="detail" style={{ marginTop: 8, color: "var(--red)", fontWeight: 600 }}>
            {moneyCompact(m.shortfall)} more to unlock {money(m.reward_value)}
          </div>
        )}
        {m.status === "lost_not_enrolled" && (
          <div className="detail" style={{ marginTop: 8, color: "var(--red)", fontWeight: 600 }}>
            Threshold crossed but not enrolled — enrol to claim.
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="card">
      <div className="name" style={{ justifyContent: "space-between", display: "flex" }}>
        <span>{m.name}</span><span className={`pill ${statusPill}`}>{m.status.replace(/_/g, " ")}</span>
      </div>
      <div className="detail" style={{ marginTop: 6 }}>Monthly · {money(m.reward_value)}/mo</div>
      <div style={{ display: "flex", gap: 14, marginTop: 8 }}>
        <div><div style={{ fontSize: 20, fontWeight: 800, color: "var(--green)" }}>{m.achieved_months}</div><div className="detail">earned</div></div>
        <div><div style={{ fontSize: 20, fontWeight: 800, color: "var(--amber)" }}>{m.near_miss_months}</div><div className="detail">near-miss</div></div>
        {m.lost_months > 0 && <div><div style={{ fontSize: 20, fontWeight: 800, color: "var(--red)" }}>{m.lost_months}</div><div className="detail">lost</div></div>}
      </div>
    </div>
  );
}
