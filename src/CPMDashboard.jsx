import { useState, useEffect } from "react";
import {
  Home, AlertTriangle, Building2, Users, ChevronRight,
  Moon, Sun, RefreshCw, TrendingUp, DollarSign,
  BarChart3, Loader
} from "lucide-react";

const fmt = (n) => n < 0
  ? `-$${Math.abs(n).toLocaleString()}`
  : `$${n.toLocaleString()}`;

export default function CPMDashboard() {
  const [data, setData]               = useState(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [dark, setDark]               = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [page, setPage]               = useState("overview");
  const [complexFilter, setComplexFilter] = useState("all");

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetch("./dashboard_data.json")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { console.log("financials:", d.financials); setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  };

  useEffect(() => { loadData(); }, []);

  const t = dark
    ? { bg: "#0d1117", surface: "#161b22", border: "#30363d", text: "#e6edf3", muted: "#8b949e", accent: "#58a6ff", danger: "#f85149", success: "#3fb950", warn: "#d29922" }
    : { bg: "#f6f8fa", surface: "#ffffff",  border: "#d0d7de", text: "#24292f", muted: "#656d76", accent: "#0969da", danger: "#cf222e", success: "#1a7f37", warn: "#9a6700" };

  // Derived totals (safe while loading)
  const complexes      = data?.complexes ?? [];
  const flaggedOwners  = data?.flagged   ?? [];
  const allOwners      = data?.allOwners ?? [];

  const totalOwners    = complexes.reduce((s, c) => s + c.owners, 0);
  const totalFlagged   = complexes.reduce((s, c) => s + c.flagged, 0);
  const totalRentMTD   = complexes.reduce((s, c) => s + c.totalRent, 0);
  const avgRentPortfolio = totalOwners > 0
    ? Math.round(complexes.reduce((s, c) => s + c.avgRent * c.owners, 0) / totalOwners)
    : 0;

  const filteredFlagged = complexFilter === "all"
    ? flaggedOwners
    : flaggedOwners.filter((o) => o.complex === complexFilter);

  const navItems = [
    { id: "overview",   icon: Home,         label: "Overview"           },
    { id: "flagged",    icon: AlertTriangle, label: "Flagged Owners", badge: totalFlagged || null },
    { id: "complexes",  icon: Building2,     label: "By Complex"         },
    { id: "financials", icon: DollarSign,    label: "Business Financials" },
    { id: "owners",     icon: Users,         label: "All Owners"         },
  ];

  // Formatted timestamp from JSON
  const updatedLabel = data?.updated
    ? (() => {
        const d = new Date(data.updated);
        return d.toLocaleString("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true });
      })()
    : null;

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: t.bg, fontFamily: "'DM Mono', 'Fira Code', monospace", color: t.text, fontSize: 13 }}>

      {/* Sidebar */}
      <nav style={{
        width: sidebarOpen ? 220 : 56, flexShrink: 0, background: t.surface,
        borderRight: `1px solid ${t.border}`, display: "flex", flexDirection: "column",
        transition: "width 0.25s ease", overflow: "hidden", position: "sticky", top: 0, height: "100vh"
      }}>
        <div style={{ padding: "18px 14px 14px", borderBottom: `1px solid ${t.border}`, display: "flex", alignItems: "center", gap: 10, overflow: "hidden" }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: t.accent, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <BarChart3 size={15} color="#fff" />
          </div>
          {sidebarOpen && <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-0.3px", whiteSpace: "nowrap", color: t.text }}>CPM</span>}
        </div>

        <div style={{ flex: 1, padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {navItems.map((item) => {
            const active = page === item.id;
            return (
              <button key={item.id} onClick={() => setPage(item.id)} style={{
                display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
                borderRadius: 6, border: "none", cursor: "pointer", width: "100%", textAlign: "left",
                background: active ? (dark ? "rgba(88,166,255,0.1)" : "rgba(9,105,218,0.08)") : "transparent",
                color: active ? t.accent : t.muted, fontFamily: "inherit", fontSize: 13, fontWeight: active ? 600 : 400,
                transition: "all 0.15s", whiteSpace: "nowrap", overflow: "hidden"
              }}>
                <item.icon size={16} style={{ flexShrink: 0 }} />
                {sidebarOpen && <span style={{ flex: 1 }}>{item.label}</span>}
                {sidebarOpen && item.badge && (
                  <span style={{ background: t.danger, color: "#fff", borderRadius: 10, padding: "1px 7px", fontSize: 11, fontWeight: 700 }}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{
          display: "flex", alignItems: "center", gap: 10, padding: "12px 18px",
          borderTop: `1px solid ${t.border}`, border: "none", background: "transparent",
          color: t.muted, cursor: "pointer", fontFamily: "inherit", fontSize: 12
        }}>
          <ChevronRight size={16} style={{ transform: sidebarOpen ? "rotate(180deg)" : "none", transition: "0.25s", flexShrink: 0 }} />
          {sidebarOpen && <span>Collapse</span>}
        </button>
      </nav>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* Topbar */}
        <div style={{ background: t.surface, borderBottom: `1px solid ${t.border}`, padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 10 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.3px" }}>
              {navItems.find((n) => n.id === page)?.label}
            </div>
            <div style={{ color: t.muted, fontSize: 11, marginTop: 1 }}>
              {data?.month ?? "—"}
              {updatedLabel && ` · Updated ${updatedLabel}`}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={loadData} style={{ background: "transparent", border: `1px solid ${t.border}`, borderRadius: 6, padding: "6px 10px", color: t.muted, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontFamily: "inherit" }}>
              <RefreshCw size={13} /> Refresh
            </button>
            <button onClick={() => setDark(!dark)} style={{ background: "transparent", border: `1px solid ${t.border}`, borderRadius: 6, padding: "7px 8px", color: t.muted, cursor: "pointer", display: "flex" }}>
              {dark ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, padding: 24, overflowY: "auto" }}>

          {/* Loading */}
          {loading && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 320, gap: 16, color: t.muted }}>
              <Loader size={28} style={{ animation: "spin 1s linear infinite" }} />
              <span style={{ fontSize: 13 }}>Loading dashboard data…</span>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div style={{ background: `rgba(248,81,73,0.08)`, border: `1px solid ${t.danger}`, borderRadius: 8, padding: "20px 24px", color: t.danger }}>
              <strong>Failed to load dashboard_data.json</strong>
              <div style={{ marginTop: 6, fontSize: 12, color: t.muted }}>{error}</div>
            </div>
          )}

          {/* OVERVIEW */}
          {!loading && !error && page === "overview" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 24 }}>
                {[
                  { label: "Total Owners",      value: totalOwners,                           sub: `${complexes.length} complexes`,                            icon: Users,       color: t.accent  },
                  { label: "Flagged MTD",        value: totalFlagged,                          sub: `${totalOwners ? Math.round(totalFlagged/totalOwners*100) : 0}% of portfolio`, icon: AlertTriangle, color: t.danger  },
                  { label: "Rent Received MTD",  value: `$${(totalRentMTD/1000).toFixed(0)}k`, sub: `month to date — ${data?.month}`,                          icon: DollarSign,  color: t.success },
                  { label: "Portfolio Avg Rent", value: `$${avgRentPortfolio}`,                sub: "per unit / week",                                          icon: TrendingUp,  color: t.warn    },
                ].map((s, i) => (
                  <div key={i} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, padding: "18px 20px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                      <span style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px" }}>{s.label}</span>
                      <s.icon size={15} color={s.color} />
                    </div>
                    <div style={{ fontSize: 26, fontWeight: 700, color: s.color, letterSpacing: "-0.5px" }}>{s.value}</div>
                    <div style={{ color: t.muted, fontSize: 11, marginTop: 4 }}>{s.sub}</div>
                  </div>
                ))}
              </div>

              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, marginBottom: 24 }}>
                <div style={{ padding: "14px 20px", borderBottom: `1px solid ${t.border}`, fontWeight: 600, fontSize: 13 }}>Complexes — {data?.month}</div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                      {["Complex","Owners","Avg Rent","Flagged","Rent MTD","Bills MTD","Net MTD"].map((h) => (
                        <th key={h} style={{ padding: "10px 20px", textAlign: h === "Complex" ? "left" : "right", fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {complexes.map((c, i) => {
                      const net = c.totalRent - c.totalBills;
                      return (
                        <tr key={c.code} style={{ borderTop: `1px solid ${t.border}`, background: i % 2 === 0 ? "transparent" : (dark ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)") }}>
                          <td style={{ padding: "11px 20px", fontWeight: 600 }}>{c.name}</td>
                          <td style={{ padding: "11px 20px", textAlign: "right", color: t.muted }}>{c.owners}</td>
                          <td style={{ padding: "11px 20px", textAlign: "right" }}>${c.avgRent}</td>
                          <td style={{ padding: "11px 20px", textAlign: "right" }}>
                            <span style={{ color: c.flagged > 8 ? t.danger : c.flagged > 4 ? t.warn : t.success, fontWeight: 600 }}>{c.flagged}</span>
                          </td>
                          <td style={{ padding: "11px 20px", textAlign: "right" }}>${c.totalRent.toLocaleString()}</td>
                          <td style={{ padding: "11px 20px", textAlign: "right", color: t.muted }}>${c.totalBills.toLocaleString()}</td>
                          <td style={{ padding: "11px 20px", textAlign: "right", fontWeight: 600, color: net >= 0 ? t.success : t.danger }}>
                            {net >= 0 ? "+" : ""}{fmt(net)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 }}>
                <div style={{ padding: "14px 20px", borderBottom: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600 }}>Worst Flagged Owners</span>
                  <button onClick={() => setPage("flagged")} style={{ background: "transparent", border: "none", color: t.accent, cursor: "pointer", fontSize: 12, fontFamily: "inherit" }}>View all →</button>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                      {["Unit","Owner","Complex","Rent","Bills","Net"].map((h) => (
                        <th key={h} style={{ padding: "9px 20px", textAlign: ["Unit","Owner","Complex"].includes(h) ? "left" : "right", fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {flaggedOwners.slice(0, 6).map((o, i) => (
                      <tr key={i} style={{ borderTop: `1px solid ${t.border}`, background: dark ? "rgba(248,81,73,0.04)" : "rgba(207,34,46,0.03)" }}>
                        <td style={{ padding: "10px 20px", color: t.muted, fontFamily: "monospace" }}>{o.code}</td>
                        <td style={{ padding: "10px 20px", fontWeight: 500 }}>{o.name}</td>
                        <td style={{ padding: "10px 20px", color: t.muted }}>{o.complex}</td>
                        <td style={{ padding: "10px 20px", textAlign: "right" }}>{o.rent === 0 ? <span style={{ color: t.danger }}>$0</span> : `$${o.rent.toLocaleString()}`}</td>
                        <td style={{ padding: "10px 20px", textAlign: "right", color: t.muted }}>${o.bills.toLocaleString()}</td>
                        <td style={{ padding: "10px 20px", textAlign: "right", fontWeight: 700, color: t.danger }}>{fmt(o.net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* FLAGGED OWNERS */}
          {!loading && !error && page === "flagged" && (
            <div>
              <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
                {["all", ...complexes.map((c) => c.name)].map((f) => (
                  <button key={f} onClick={() => setComplexFilter(f)} style={{
                    padding: "5px 14px", borderRadius: 20, border: `1px solid ${t.border}`, cursor: "pointer",
                    background: complexFilter === f ? t.accent : t.surface, color: complexFilter === f ? "#fff" : t.muted,
                    fontFamily: "inherit", fontSize: 12
                  }}>
                    {f === "all" ? "All complexes" : f}
                  </button>
                ))}
              </div>
              <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 }}>
                <div style={{ padding: "13px 20px", borderBottom: `1px solid ${t.border}`, color: t.muted, fontSize: 12 }}>
                  {filteredFlagged.length} owners where bills exceed rent received — sorted worst first
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                      {["#","Unit","Owner","Complex","Rent Received","Bills","Shortfall"].map((h) => (
                        <th key={h} style={{ padding: "9px 20px", textAlign: ["#","Unit","Owner","Complex"].includes(h) ? "left" : "right", fontWeight: 500 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFlagged.map((o, i) => (
                      <tr key={i} style={{ borderTop: `1px solid ${t.border}`, background: dark ? "rgba(248,81,73,0.04)" : "rgba(207,34,46,0.03)" }}>
                        <td style={{ padding: "10px 20px", color: t.muted }}>{i + 1}</td>
                        <td style={{ padding: "10px 20px", color: t.muted, fontFamily: "monospace" }}>{o.code}</td>
                        <td style={{ padding: "10px 20px", fontWeight: 500 }}>{o.name}</td>
                        <td style={{ padding: "10px 20px", color: t.muted, fontSize: 12 }}>{o.complex}</td>
                        <td style={{ padding: "10px 20px", textAlign: "right", color: o.rent === 0 ? t.danger : t.text }}>
                          {o.rent === 0 ? "—" : `$${o.rent.toLocaleString()}`}
                        </td>
                        <td style={{ padding: "10px 20px", textAlign: "right", color: t.muted }}>${o.bills.toLocaleString()}</td>
                        <td style={{ padding: "10px 20px", textAlign: "right", fontWeight: 700, color: t.danger }}>{fmt(o.net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* BY COMPLEX */}
          {!loading && !error && page === "complexes" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
              {complexes.map((c) => {
                const pct = c.owners > 0 ? Math.round(c.flagged / c.owners * 100) : 0;
                const net = c.totalRent - c.totalBills;
                return (
                  <div key={c.code} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, padding: 20 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>{c.name}</div>
                        <div style={{ color: t.muted, fontSize: 11 }}>Complex {c.code} · {c.owners} owners</div>
                      </div>
                      <span style={{ background: c.flagged > 8 ? "rgba(248,81,73,0.12)" : "rgba(63,185,80,0.12)", color: c.flagged > 8 ? t.danger : t.success, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                        {c.flagged} flagged
                      </span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
                      {[
                        { label: "Avg Rent",  value: `$${c.avgRent}/wk` },
                        { label: "Rent MTD",  value: `$${c.totalRent.toLocaleString()}` },
                        { label: "Bills MTD", value: `$${c.totalBills.toLocaleString()}` },
                        { label: "Net MTD",   value: fmt(net), color: net >= 0 ? t.success : t.danger },
                      ].map((s) => (
                        <div key={s.label} style={{ background: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.03)", borderRadius: 6, padding: "10px 12px" }}>
                          <div style={{ color: t.muted, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.4px", marginBottom: 4 }}>{s.label}</div>
                          <div style={{ fontWeight: 600, color: s.color || t.text }}>{s.value}</div>
                        </div>
                      ))}
                    </div>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                        <span style={{ color: t.muted, fontSize: 11 }}>Flagged rate</span>
                        <span style={{ color: pct > 40 ? t.danger : t.muted, fontSize: 11, fontWeight: 600 }}>{pct}%</span>
                      </div>
                      <div style={{ height: 4, background: dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)", borderRadius: 2 }}>
                        <div style={{ height: 4, width: `${pct}%`, borderRadius: 2, background: pct > 40 ? t.danger : pct > 25 ? t.warn : t.success, transition: "width 0.4s ease" }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* BUSINESS FINANCIALS */}
          {!loading && !error && page === "financials" && (() => {
            const f = data?.financials ?? {};
            const mgmtFees   = f.management_fees ?? 0;
            const otherIncome = Math.max(0, (f.total_income ?? 0) - mgmtFees);
            const otherExp   = Math.max(0, (f.total_expenses ?? 0) - (f.loan_interest ?? 0) - (f.wages ?? 0));
            const netColor   = (f.net_profit ?? 0) >= 0 ? t.success : "#C00000";
            const panel = { background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" };
            const panelHead = { padding: "13px 20px", borderBottom: `1px solid ${t.border}`, fontWeight: 600, fontSize: 13 };
            const tr = (label, value, bold) => (
              <tr style={{ borderTop: `1px solid ${t.border}` }}>
                <td style={{ padding: "11px 20px", color: bold ? t.text : t.muted, fontWeight: bold ? 700 : 400 }}>{label}</td>
                <td style={{ padding: "11px 20px", textAlign: "right", fontWeight: bold ? 700 : 400, color: bold ? t.text : t.muted }}>{fmt(value)}</td>
              </tr>
            );
            return (
              <div>
                {/* Stat cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 24 }}>
                  {[
                    { label: "Cash Balance",           value: f.cash_balance           ?? 0, color: t.success  },
                    { label: "MTD Income",              value: f.total_income           ?? 0, color: t.accent   },
                    { label: "MTD Expenses",            value: f.total_expenses         ?? 0, color: "#C00000"  },
                    { label: "Net Profit",              value: f.net_profit             ?? 0, color: netColor   },
                    { label: "Invoices Due This Month", value: f.invoices_due_this_month ?? 0, color: t.warn    },
                  ].map((s) => (
                    <div key={s.label} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, padding: "18px 20px" }}>
                      <div style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 10 }}>{s.label}</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: s.color, letterSpacing: "-0.5px" }}>{fmt(Math.round(s.value))}</div>
                      <div style={{ height: 3, marginTop: 14, borderRadius: 2, background: s.color, opacity: 0.25 }} />
                    </div>
                  ))}
                </div>

                {/* Breakdown panels */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
                  {/* Income */}
                  <div style={panel}>
                    <div style={panelHead}>Income Breakdown</div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <tbody>
                        {tr("Management Fees",       mgmtFees)}
                        {tr("Body Corporate / Other", otherIncome)}
                        {tr("Total Income",           f.total_income ?? 0, true)}
                      </tbody>
                    </table>
                  </div>

                  {/* Expenses */}
                  <div style={panel}>
                    <div style={panelHead}>Expense Breakdown</div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <tbody>
                        {tr("Loan Interest",   f.loan_interest ?? 0)}
                        {tr("Wages",           f.wages         ?? 0)}
                        {tr("Other Expenses",  otherExp)}
                        {tr("Total Expenses",  f.total_expenses ?? 0, true)}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Invoices due */}
                {(f.top_invoices ?? []).length > 0 && (
                  <div style={{ ...panel, marginBottom: 20 }}>
                    <div style={{ ...panelHead, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>Invoices Due This Month</span>
                      <span style={{ color: t.muted, fontWeight: 400, fontSize: 12 }}>
                        {f.invoices_due_count} invoices · {fmt(Math.round(f.invoices_due_this_month ?? 0))} total
                        {(f.overdue_total ?? 0) > 0 && (
                          <span style={{ color: "#C00000", marginLeft: 12 }}>· {fmt(Math.round(f.overdue_total))} overdue</span>
                        )}
                      </span>
                    </div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                          <th style={{ padding: "9px 20px", textAlign: "left",  fontWeight: 500 }}>Contact</th>
                          <th style={{ padding: "9px 20px", textAlign: "right", fontWeight: 500 }}>Amount Due</th>
                          <th style={{ padding: "9px 20px", textAlign: "right", fontWeight: 500 }}>Due Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(f.top_invoices ?? []).map((inv, i) => {
                          const overdue = inv.due_date < new Date().toISOString().slice(0, 10);
                          return (
                            <tr key={i} style={{
                              borderTop: `1px solid ${t.border}`,
                              background: overdue ? (dark ? "rgba(192,0,0,0.06)" : "rgba(192,0,0,0.04)") : "transparent"
                            }}>
                              <td style={{ padding: "10px 20px", fontWeight: overdue ? 600 : 400, color: overdue ? "#C00000" : t.text }}>{inv.contact_name}</td>
                              <td style={{ padding: "10px 20px", textAlign: "right" }}>{fmt(inv.amount_due)}</td>
                              <td style={{ padding: "10px 20px", textAlign: "right", color: overdue ? "#C00000" : t.muted, fontWeight: overdue ? 600 : 400 }}>{inv.due_date}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <div style={{ color: t.muted, fontSize: 11, fontStyle: "italic", textAlign: "center" }}>
                  Management fees are disbursed at month end. Mid-month figures will reflect partial income.
                </div>
              </div>
            );
          })()}

          {/* ALL OWNERS */}
          {!loading && !error && page === "owners" && (
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 }}>
              <div style={{ padding: "13px 20px", borderBottom: `1px solid ${t.border}`, color: t.muted, fontSize: 12 }}>
                {allOwners.length} owners · {totalFlagged} flagged · sorted by complex
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                    {["Unit","Owner","Complex","Rent Received","Bills","Net"].map((h) => (
                      <th key={h} style={{ padding: "9px 20px", textAlign: ["Unit","Owner","Complex"].includes(h) ? "left" : "right", fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allOwners.map((o, i) => (
                    <tr key={i} style={{
                      borderTop: `1px solid ${t.border}`,
                      background: o.net < 0
                        ? (dark ? "rgba(248,81,73,0.04)" : "rgba(207,34,46,0.03)")
                        : (i % 2 === 0 ? "transparent" : (dark ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)"))
                    }}>
                      <td style={{ padding: "9px 20px", color: t.muted, fontFamily: "monospace", fontSize: 12 }}>{o.code}</td>
                      <td style={{ padding: "9px 20px", fontWeight: o.net < 0 ? 600 : 400 }}>{o.name}</td>
                      <td style={{ padding: "9px 20px", color: t.muted, fontSize: 12 }}>{o.complex}</td>
                      <td style={{ padding: "9px 20px", textAlign: "right" }}>{o.rent === 0 ? <span style={{ color: t.danger }}>$0</span> : `$${o.rent.toLocaleString()}`}</td>
                      <td style={{ padding: "9px 20px", textAlign: "right", color: t.muted }}>${o.bills.toLocaleString()}</td>
                      <td style={{ padding: "9px 20px", textAlign: "right", fontWeight: 600, color: o.net < 0 ? t.danger : t.success }}>{fmt(o.net)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
