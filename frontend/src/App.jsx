import { useEffect, useState } from "react";
import { api } from "./api";
import MemberDashboard from "./components/MemberDashboard.jsx";
import PortfolioDashboard from "./components/PortfolioDashboard.jsx";

export default function App() {
  const [tab, setTab] = useState("member");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="logo">R</div>
          <div>
            <h1>ReclaimIQ</h1>
            <p>Benefit-Underutilization Analytics · CodeStreet 2026</p>
          </div>
        </div>
        <div className="tabs">
          <button className={tab === "member" ? "active" : ""} onClick={() => setTab("member")}>
            Card Member
          </button>
          <button className={tab === "portfolio" ? "active" : ""} onClick={() => setTab("portfolio")}>
            Issuer Portfolio
          </button>
        </div>
      </header>

      <main className="container">
        {health && health.status === "down" && (
          <div className="card" style={{ borderColor: "#f3c1c1", background: "#fff6f6" }}>
            <b>API not reachable.</b> Start the backend: <code>uvicorn app.main:app --port 8000</code>
          </div>
        )}
        {tab === "member" ? <MemberDashboard /> : <PortfolioDashboard />}
      </main>
    </div>
  );
}
