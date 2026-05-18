import { useState, useEffect } from "react";
import {
  Home, AlertTriangle, Building2, Users, ChevronRight,
  Moon, Sun, RefreshCw, TrendingUp, DollarSign,
  BarChart3, Loader, ClipboardList
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

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
  const [isMobile, setIsMobile]       = useState(window.innerWidth <= 768);
  const [menuOpen, setMenuOpen]       = useState(false);

  const loadData = () => {
    setLoading(true);
    setError(null);
    fetch("./dashboard_data.json")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  };

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const t = dark
    ? { bg: "#0d1117", surface: "#161b22", border: "#30363d", text: "#e6edf3", muted: "#8b949e", accent: "#58a6ff", danger: "#f85149", success: "#3fb950", warn: "#d29922" }
    : { bg: "#f4f5f7", surface: "#ffffff",  border: "#dde1e7", text: "#1e2a3a", muted: "#656d76", accent: "#0969da", danger: "#CC0000", success: "#1a7f37", warn: "#9a6700" };

  const complexes      = data?.complexes    ?? [];
  const flaggedOwners  = data?.flagged      ?? [];
  const allOwners      = data?.allOwners    ?? [];
  const inspections    = data?.inspections  ?? null;

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
    { id: "overview",     icon: Home,          label: "Overview"            },
    { id: "flagged",      icon: AlertTriangle,  label: "Flagged Owners",    badge: totalFlagged || null },
    { id: "complexes",    icon: Building2,      label: "By Complex"          },
    { id: "financials",   icon: DollarSign,     label: "Business Financials" },
    { id: "owners",       icon: Users,          label: "All Owners"          },
    { id: "inspections",  icon: ClipboardList,  label: "Inspections",        badge: inspections?.summary?.total_overdue || null },
  ];

  const updatedLabel = data?.updated
    ? (() => {
        const d = new Date(data.updated);
        return d.toLocaleString("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true });
      })()
    : null;

  // Navigate and close mobile menu
  const navigate = (id) => { setPage(id); setMenuOpen(false); };

  // Responsive helpers
  const gap   = isMobile ? 12 : 16;
  const cp    = isMobile ? "14px 14px" : "20px 22px";   // card padding
  const tp    = isMobile ? "8px 10px"  : "11px 20px";   // table cell padding
  const valFz = isMobile ? 22 : 28;                      // stat value font size

  const logoSrc = dark ? "./cpm-logo-light.svg" : "./cpm-logo-dark.svg";

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: t.bg, fontFamily: "Arial, sans-serif", color: t.text, fontSize: 13 }}>

      {/* ── Sidebar — desktop only ── */}
      {!isMobile && (
        <nav style={{
          width: sidebarOpen ? 240 : 64, flexShrink: 0, background: t.surface,
          borderRight: `1px solid ${t.border}`, display: "flex", flexDirection: "column",
          transition: "width 0.25s ease", overflow: "hidden", position: "sticky", top: 0, height: "100vh"
        }}>
          <div style={{ padding: "16px 16px 14px", borderBottom: `1px solid ${t.border}`, display: "flex", alignItems: "center", overflow: "hidden" }}>
            {sidebarOpen
              ? <img src={logoSrc} alt="CPM" style={{ height: 52, width: "auto", objectFit: "contain" }} />
              : <img src={logoSrc} alt="CPM" style={{ height: 38, width: 38, objectFit: "contain" }} />
            }
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
      )}

      {/* ── Main column ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

        {/* ── Topbar ── */}
        <div style={{
          background: t.surface, borderBottom: `1px solid ${t.border}`,
          position: "sticky", top: 0, zIndex: 110,
          display: "flex", alignItems: "center",
          minHeight: isMobile ? 48 : 56,
          padding: isMobile ? "0 12px" : "0 24px",
          gap: isMobile ? 10 : 0,
          justifyContent: "space-between",
        }}>
          {isMobile ? (
            /* ── Mobile topbar ── */
            <>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                style={{ background: "transparent", border: "none", color: t.text, cursor: "pointer", fontSize: 22, lineHeight: 1, padding: "4px 6px", flexShrink: 0 }}
                aria-label="Menu"
              >
                {menuOpen ? "✕" : "☰"}
              </button>

              <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
                {page === "overview"
                  ? <img src={logoSrc} alt="CPM" style={{ height: 30, objectFit: "contain" }} />
                  : <span style={{ fontWeight: 700, fontSize: 15 }}>{navItems.find((n) => n.id === page)?.label}</span>
                }
              </div>

              <button
                onClick={loadData}
                style={{ background: "transparent", border: `1px solid ${t.border}`, borderRadius: 6, padding: "6px 8px", color: t.muted, cursor: "pointer", display: "flex", alignItems: "center", flexShrink: 0 }}
                aria-label="Refresh"
              >
                <RefreshCw size={14} />
              </button>
            </>
          ) : (
            /* ── Desktop topbar ── */
            <>
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
            </>
          )}
        </div>

        {/* ── Mobile nav dropdown ── */}
        {isMobile && menuOpen && (
          <>
            {/* Backdrop */}
            <div
              onClick={() => setMenuOpen(false)}
              style={{ position: "fixed", inset: 0, zIndex: 99, background: "rgba(0,0,0,0.35)" }}
            />
            {/* Menu panel */}
            <div style={{
              position: "fixed", top: 48, left: 0, right: 0, zIndex: 100,
              background: t.surface, borderBottom: `1px solid ${t.border}`,
              boxShadow: "0 6px 24px rgba(0,0,0,0.25)"
            }}>
              {navItems.map((item) => {
                const active = page === item.id;
                return (
                  <button key={item.id} onClick={() => navigate(item.id)} style={{
                    display: "flex", alignItems: "center", gap: 14,
                    width: "100%", padding: "15px 20px", border: "none",
                    borderTop: `1px solid ${t.border}`,
                    background: active ? (dark ? "rgba(88,166,255,0.08)" : "rgba(9,105,218,0.06)") : "transparent",
                    color: active ? t.accent : t.text,
                    fontFamily: "inherit", fontSize: 15, fontWeight: active ? 700 : 400,
                    cursor: "pointer", textAlign: "left",
                  }}>
                    <item.icon size={18} style={{ flexShrink: 0, color: active ? t.accent : t.muted }} />
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.badge && (
                      <span style={{ background: "#CC0000", color: "#fff", borderRadius: 10, padding: "2px 8px", fontSize: 12, fontWeight: 700 }}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </>
        )}

        {/* ── Content ── */}
        <div style={{
          flex: 1, padding: isMobile ? 12 : 24, overflowY: "auto",
          paddingBottom: isMobile ? "calc(12px + env(safe-area-inset-bottom))" : 24,
        }}>

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

          {/* ══════════════════════════════════════════
              OVERVIEW
          ══════════════════════════════════════════ */}
          {!loading && !error && page === "overview" && (() => {
            const f   = data?.financials ?? {};
            const nwc = (f.cash_balance ?? 0) + (f.receivables_total ?? 0) - (f.payables_total ?? 0);
            const nwcColor = nwc >= 0 ? "#1a7f37" : "#CC0000";
            const totalUnits = complexes.reduce((s, c) => s + c.owners, 0);
            const weightedAvgRent = totalUnits > 0
              ? Math.round(complexes.reduce((s, c) => s + c.avgRent * c.owners, 0) / totalUnits)
              : 0;
            const card = { background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 };
            const lbl  = { color: t.muted, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 8, fontWeight: 500 };
            const val  = { fontSize: valFz, fontWeight: 700, letterSpacing: "-0.5px", marginBottom: 8 };

            return (
              <div>
                {/* Row 1: 5 stat cards — 2-col on mobile */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5,1fr)", gap, marginBottom: gap }}>

                  <div style={{ ...card, borderTop: "3px solid #1a7f37", padding: cp }}>
                    <div style={lbl}>Cash in Bank</div>
                    <div style={{ ...val, color: "#1a7f37" }}>{fmt(Math.round(f.cash_balance ?? 0))}</div>
                    <div style={{ color: t.muted, fontSize: 11 }}>Bank accounts</div>
                  </div>

                  <div style={{ ...card, borderTop: "3px solid #1e2a3a", padding: cp }}>
                    <div style={lbl}>Net Working Capital</div>
                    <div style={{ ...val, color: nwcColor }}>{fmt(Math.round(nwc))}</div>
                    {!isMobile && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        <div style={{ fontSize: 11, color: "#1a7f37" }}>+ {fmt(Math.round(f.cash_balance ?? 0))} cash</div>
                        <div style={{ fontSize: 11, color: "#1a7f37" }}>+ {fmt(Math.round(f.receivables_total ?? 0))} receivables</div>
                        <div style={{ fontSize: 11, color: "#CC0000" }}>− {fmt(Math.round(f.payables_total ?? 0))} payables</div>
                      </div>
                    )}
                  </div>

                  <div style={{ ...card, borderTop: "3px solid #1e2a3a", padding: cp }}>
                    <div style={lbl}>Total Units</div>
                    <div style={{ ...val, color: t.text }}>{totalUnits}</div>
                    <div style={{ color: t.muted, fontSize: 11 }}>across {complexes.length} complexes</div>
                  </div>

                  <div style={{ ...card, borderTop: "3px solid #1e2a3a", padding: cp }}>
                    <div style={lbl}>Avg Rent</div>
                    <div style={{ ...val, color: t.text }}>${weightedAvgRent}/wk</div>
                    <div style={{ color: t.muted, fontSize: 11 }}>per unit per week</div>
                  </div>

                  {(() => {
                    const od  = inspections?.summary?.total_overdue  ?? null;
                    const ffl = inspections?.summary?.total_frequency_flags ?? 0;
                    const color = od === null ? t.muted : od > 0 ? "#CC0000" : ffl > 0 ? t.warn : "#1a7f37";
                    return (
                      <div
                        onClick={() => navigate("inspections")}
                        style={{ ...card, borderTop: `3px solid ${color}`, padding: cp, cursor: "pointer" }}
                      >
                        <div style={lbl}>Inspections Overdue</div>
                        <div style={{ ...val, color }}>
                          {od === null ? "—" : od}
                        </div>
                        <div style={{ color: t.muted, fontSize: 11 }}>
                          {od === null
                            ? "no data yet"
                            : od === 0 && ffl === 0
                              ? "all clear ✓"
                              : od === 0
                                ? `${ffl} frequency flag${ffl !== 1 ? "s" : ""}`
                                : `${od === 1 ? "property" : "properties"} overdue`}
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Middle: Complex table + Needs Attention — stacked on mobile */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "3fr 2fr", gap }}>

                  {/* Complex performance table */}
                  <div style={{ ...card, overflow: "hidden" }}>
                    <div style={{ padding: "14px 16px", borderBottom: `1px solid ${t.border}`, fontWeight: 600, fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>Complex Performance — {data?.month}</span>
                      <span style={{ color: t.muted, fontWeight: 400, fontSize: 12 }}>{totalUnits} units</span>
                    </div>
                    <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
                      <table style={{ width: "100%", minWidth: 320, borderCollapse: "collapse" }}>
                        <thead>
                          <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                            {["Complex", "Units", "Avg Rent", "Rent Change"].map((h) => (
                              <th key={h} style={{ padding: tp, textAlign: h === "Complex" ? "left" : "right", fontWeight: 500, whiteSpace: "nowrap" }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                            const main    = complexes.filter(c => c.code !== "99");
                            const outside = complexes.find(c => c.code === "99");
                            const renderRow = (c, i, divider) => {
                              const pct = c.rentChangePct;
                              const changeEl = pct == null
                                ? <span style={{ color: t.muted }}>—</span>
                                : pct >= 0
                                  ? <span style={{ color: "#1a7f37", fontWeight: 600 }}>↑ +{pct.toFixed(1)}%</span>
                                  : <span style={{ color: "#CC0000", fontWeight: 600 }}>↓ {pct.toFixed(1)}%</span>;
                              return (
                                <tr key={c.code} style={{
                                  borderTop: divider ? `2px solid ${t.border}` : `1px solid ${t.border}`,
                                  background: divider
                                    ? (dark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)")
                                    : (i % 2 === 0 ? "transparent" : (dark ? "rgba(255,255,255,0.015)" : "rgba(0,0,0,0.015)"))
                                }}>
                                  <td style={{ padding: tp, fontWeight: 600, color: divider ? t.muted : t.text, whiteSpace: "nowrap" }}>{c.name}</td>
                                  <td style={{ padding: tp, textAlign: "right", color: t.muted }}>{c.owners}</td>
                                  <td style={{ padding: tp, textAlign: "right", color: divider ? t.muted : t.text, whiteSpace: "nowrap" }}>${c.avgRent}/wk</td>
                                  <td style={{ padding: tp, textAlign: "right", whiteSpace: "nowrap" }}>{changeEl}</td>
                                </tr>
                              );
                            };
                            return [
                              ...main.map((c, i) => renderRow(c, i, false)),
                              ...(outside ? [renderRow(outside, 0, true)] : []),
                            ];
                          })()}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Needs Attention panel */}
                  <div style={{ ...card, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                    <div style={{ padding: "14px 16px", borderBottom: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: 600, fontSize: 13 }}>
                      <span>Needs Attention</span>
                      {totalFlagged > 0 && (
                        <span style={{ background: "#CC0000", color: "#fff", borderRadius: 12, padding: "2px 9px", fontSize: 11, fontWeight: 700 }}>{totalFlagged}</span>
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      {flaggedOwners.length === 0 && (
                        <div style={{ padding: "20px 16px", color: t.muted, fontSize: 12 }}>No flagged owners this month.</div>
                      )}
                      {flaggedOwners.slice(0, 5).map((o, i) => (
                        <div key={i} style={{ padding: `13px 16px`, borderTop: i > 0 ? `1px solid ${t.border}` : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{o.name}</div>
                            <div style={{ fontFamily: "monospace", fontSize: 11, color: t.muted }}>{o.code} · {o.complex}</div>
                          </div>
                          <div style={{ color: "#CC0000", fontWeight: 700, fontSize: 14, flexShrink: 0 }}>{fmt(Math.round(o.net))}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ padding: "12px 16px", borderTop: `1px solid ${t.border}` }}>
                      <button onClick={() => navigate("flagged")} style={{ background: "transparent", border: "none", color: "#CC0000", cursor: "pointer", fontSize: 12, fontFamily: "inherit", fontWeight: 600, padding: 0 }}>
                        View all {flaggedOwners.length} flagged →
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ══════════════════════════════════════════
              FLAGGED OWNERS
          ══════════════════════════════════════════ */}
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
                <div style={{ padding: "13px 16px", borderBottom: `1px solid ${t.border}`, color: t.muted, fontSize: 12 }}>
                  {filteredFlagged.length} owners where bills exceed rent received — sorted worst first
                </div>
                <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
                  <table style={{ width: "100%", minWidth: 480, borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                        {["#","Unit","Owner","Complex","Rent","Bills","Shortfall"].map((h) => (
                          <th key={h} style={{ padding: tp, textAlign: ["#","Unit","Owner","Complex"].includes(h) ? "left" : "right", fontWeight: 500, whiteSpace: "nowrap" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredFlagged.map((o, i) => (
                        <tr key={i} style={{ borderTop: `1px solid ${t.border}`, background: dark ? "rgba(248,81,73,0.04)" : "rgba(207,34,46,0.03)" }}>
                          <td style={{ padding: tp, color: t.muted }}>{i + 1}</td>
                          <td style={{ padding: tp, color: t.muted, fontFamily: "monospace", whiteSpace: "nowrap" }}>{o.code}</td>
                          <td style={{ padding: tp, fontWeight: 500 }}>{o.name}</td>
                          <td style={{ padding: tp, color: t.muted, fontSize: 12, whiteSpace: "nowrap" }}>{o.complex}</td>
                          <td style={{ padding: tp, textAlign: "right", color: o.rent === 0 ? t.danger : t.text, whiteSpace: "nowrap" }}>
                            {o.rent === 0 ? "—" : `$${o.rent.toLocaleString()}`}
                          </td>
                          <td style={{ padding: tp, textAlign: "right", color: t.muted, whiteSpace: "nowrap" }}>${o.bills.toLocaleString()}</td>
                          <td style={{ padding: tp, textAlign: "right", fontWeight: 700, color: t.danger, whiteSpace: "nowrap" }}>{fmt(o.net)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════
              BY COMPLEX
          ══════════════════════════════════════════ */}
          {!loading && !error && page === "complexes" && (
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3,1fr)", gap }}>
              {complexes.map((c) => {
                const pct = c.owners > 0 ? Math.round(c.flagged / c.owners * 100) : 0;
                const net = c.totalRent - c.totalBills;
                return (
                  <div key={c.code} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, padding: 16 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>{c.name}</div>
                        <div style={{ color: t.muted, fontSize: 11 }}>Complex {c.code} · {c.owners} owners</div>
                      </div>
                      <span style={{ background: c.flagged > 8 ? "rgba(248,81,73,0.12)" : "rgba(63,185,80,0.12)", color: c.flagged > 8 ? t.danger : t.success, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, whiteSpace: "nowrap", marginLeft: 8 }}>
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

          {/* ══════════════════════════════════════════
              BUSINESS FINANCIALS
          ══════════════════════════════════════════ */}
          {!loading && !error && page === "financials" && (() => {
            const f         = data?.financials ?? {};
            const netColor  = (f.net_profit ?? 0) >= 0 ? t.success : "#C00000";
            const panel     = { background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, overflow: "hidden" };
            const panelHead = { padding: "13px 16px", borderBottom: `1px solid ${t.border}`, fontWeight: 600, fontSize: 13 };

            const donutData = [
              { name: "Income",   value: f.total_income   ?? 0, color: "#1a7f37" },
              { name: "Expenses", value: f.total_expenses ?? 0, color: "#C00000" },
            ];

            const wageEmp   = f.wages_employee  ?? 0;
            const wageMgmt  = f.wages_management ?? 0;
            const wageOther = Math.max(0, (f.wages ?? 0) - wageEmp - wageMgmt);
            const wageRows  = [
              { label: "Staff Wages",  value: wageEmp,   color: "#1e2a3a" },
              ...(wageMgmt  > 0 ? [{ label: "Director Fees", value: wageMgmt,  color: "#C00000" }] : []),
              ...(wageOther > 0 ? [{ label: "Other Wages",   value: wageOther, color: "#8b949e" }] : []),
            ];
            const totalWages  = wageEmp + wageMgmt + wageOther;
            const netPosition = (f.cash_balance ?? 0) + (f.receivables_total ?? 0) - (f.payables_total ?? 0);

            return (
              <div>
                {/* Row 1: 3 stat cards — single col on mobile */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(3,1fr)", gap, marginBottom: gap }}>
                  {[
                    { label: "Cash Balance",   value: f.cash_balance   ?? 0, color: "#1a7f37", sub: "Bank accounts" },
                    { label: "Net Profit MTD", value: f.net_profit     ?? 0, color: netColor,  sub: `Income ${fmt(Math.round(f.total_income ?? 0))} · Exp ${fmt(Math.round(f.total_expenses ?? 0))}` },
                    { label: "Bills to Pay",   value: f.payables_total ?? 0, color: "#C00000", sub: `${f.payables_count ?? 0} invoices · ${fmt(Math.round(f.payables_overdue ?? 0))} overdue` },
                  ].map((s) => (
                    <div key={s.label} style={{ background: t.surface, borderTop: `3px solid ${s.color}`, border: `1px solid ${t.border}`, borderRadius: 8, padding: cp }}>
                      <div style={{ color: t.muted, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 8 }}>{s.label}</div>
                      <div style={{ fontSize: isMobile ? 24 : 26, fontWeight: 700, color: s.color, letterSpacing: "-0.5px", marginBottom: 6 }}>{fmt(Math.round(s.value))}</div>
                      <div style={{ color: t.muted, fontSize: 11 }}>{s.sub}</div>
                    </div>
                  ))}
                </div>

                {/* Row 2: Donut + Credit cards */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap, marginBottom: gap }}>

                  <div style={panel}>
                    <div style={panelHead}>Monthly P&amp;L Overview</div>
                    <div style={{ padding: "20px 16px", display: "flex", alignItems: "center", gap: 20, flexWrap: isMobile ? "wrap" : "nowrap" }}>
                      <div style={{ position: "relative", flexShrink: 0, width: 160, height: 160, margin: isMobile ? "0 auto" : 0 }}>
                        <ResponsiveContainer width={160} height={160}>
                          <PieChart>
                            <Pie data={donutData} cx="50%" cy="50%" innerRadius={50} outerRadius={72} dataKey="value" paddingAngle={3} startAngle={90} endAngle={-270}>
                              {donutData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                            </Pie>
                            <Tooltip formatter={(v) => fmt(Math.round(v))} contentStyle={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 6, fontSize: 12 }} />
                          </PieChart>
                        </ResponsiveContainer>
                        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
                          <div style={{ fontSize: 10, color: t.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>Net</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: netColor }}>{fmt(Math.round(f.net_profit ?? 0))}</div>
                        </div>
                      </div>
                      <div style={{ flex: 1, minWidth: 160 }}>
                        {donutData.map((d) => (
                          <div key={d.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                              <div style={{ width: 10, height: 10, borderRadius: 2, background: d.color, flexShrink: 0 }} />
                              <span style={{ color: t.muted }}>{d.name}</span>
                            </div>
                            <span style={{ fontWeight: 700, fontSize: 14, color: t.text }}>{fmt(Math.round(d.value))}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 12, marginTop: 2, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: 12, color: t.muted }}>Loan Interest</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{fmt(Math.round(f.loan_interest ?? 0))}</span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                          <span style={{ fontSize: 12, color: t.muted }}>Management Fees</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{fmt(Math.round(f.management_fees ?? 0))}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div style={panel}>
                    <div style={panelHead}>Credit Cards</div>
                    <div style={{ padding: "20px 16px" }}>
                      {[
                        { name: "Don",    balance: f.credit_card_don    ?? 0 },
                        { name: "Duncan", balance: f.credit_card_duncan ?? 0 },
                      ].map((card) => (
                        <div key={card.name} style={{ background: "linear-gradient(135deg, #1e2a3a 0%, #2d3f52 100%)", borderRadius: 10, padding: "16px 20px", marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div>
                            <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>Credit Card</div>
                            <div style={{ color: "#fff", fontWeight: 600, fontSize: 15 }}>{card.name}</div>
                          </div>
                          <div style={{ textAlign: "right" }}>
                            <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>Balance</div>
                            <div style={{ color: card.balance > 0 ? "#f85149" : "#3fb950", fontWeight: 700, fontSize: 20 }}>{fmt(Math.round(card.balance))}</div>
                          </div>
                        </div>
                      ))}
                      <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 4px 0", borderTop: `1px solid ${t.border}` }}>
                        <span style={{ fontSize: 12, color: t.muted }}>Total Credit Card Balance</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: "#f85149" }}>{fmt(Math.round((f.credit_card_don ?? 0) + (f.credit_card_duncan ?? 0)))}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Row 3: Wages + Position */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap, marginBottom: gap }}>

                  <div style={panel}>
                    <div style={panelHead}>Wages Breakdown</div>
                    <div style={{ padding: "16px 16px" }}>
                      {wageRows.map((w) => {
                        const pct = totalWages > 0 ? Math.round((w.value / totalWages) * 100) : 0;
                        return (
                          <div key={w.label} style={{ marginBottom: 18 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 7, fontSize: 12 }}>
                              <span style={{ color: t.text }}>{w.label}</span>
                              <span style={{ color: t.muted }}>{fmt(Math.round(w.value))} · {pct}%</span>
                            </div>
                            <div style={{ height: 6, borderRadius: 3, background: dark ? "#30363d" : "#e0e0e0" }}>
                              <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: w.color, transition: "width 0.4s ease" }} />
                            </div>
                          </div>
                        );
                      })}
                      {wageRows.length === 0 && <div style={{ color: t.muted, fontSize: 12 }}>No wage data this month.</div>}
                      <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 12, marginTop: 2, display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: 700 }}>
                        <span>Total Wages</span>
                        <span>{fmt(Math.round(totalWages))}</span>
                      </div>
                    </div>
                  </div>

                  <div style={panel}>
                    <div style={panelHead}>Financial Position</div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <tbody>
                        {[
                          { label: "Cash at Bank",        value: f.cash_balance      ?? 0, color: t.success, sign: 1  },
                          { label: "Invoices to Receive", value: f.receivables_total ?? 0, color: t.success, sign: 1  },
                          { label: "Bills to Pay",        value: f.payables_total    ?? 0, color: "#C00000", sign: -1 },
                        ].map(({ label, value, color, sign }) => (
                          <tr key={label} style={{ borderTop: `1px solid ${t.border}` }}>
                            <td style={{ padding: tp, color: t.muted, fontSize: 13 }}>{label}</td>
                            <td style={{ padding: tp, textAlign: "right", fontWeight: 600, color: sign > 0 ? color : "#C00000", fontSize: 13, whiteSpace: "nowrap" }}>
                              {sign < 0 ? "-" : ""}{fmt(Math.round(value))}
                            </td>
                          </tr>
                        ))}
                        <tr style={{ borderTop: `2px solid ${t.border}`, background: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)" }}>
                          <td style={{ padding: tp, fontWeight: 700, fontSize: 13 }}>Net Working Capital</td>
                          <td style={{ padding: tp, textAlign: "right", fontWeight: 700, fontSize: 16, color: netPosition >= 0 ? t.success : "#C00000", whiteSpace: "nowrap" }}>
                            {fmt(Math.round(netPosition))}
                          </td>
                        </tr>
                        <tr style={{ borderTop: `1px solid ${t.border}` }}>
                          <td style={{ padding: tp, color: t.muted, fontSize: 13 }}>Invoices This Month</td>
                          <td style={{ padding: tp, textAlign: "right", fontSize: 13, whiteSpace: "nowrap" }}>
                            <span style={{ color: t.muted, marginRight: 8 }}>{f.invoices_due_count ?? 0} inv</span>
                            <span style={{ fontWeight: 600, color: t.success }}>{fmt(Math.round(f.invoices_due_this_month ?? 0))}</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Row 4: Invoice tables */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap }}>
                  {[
                    { title: "Bills to Pay",        rows: f.top_payables    ?? [], total: f.payables_total    ?? 0, count: f.payables_count    ?? 0, overdue: f.payables_overdue    ?? 0 },
                    { title: "Invoices to Receive", rows: f.top_receivables ?? [], total: f.receivables_total ?? 0, count: f.receivables_count ?? 0, overdue: f.receivables_overdue ?? 0 },
                  ].map(({ title, rows, total, count, overdue }) => (
                    <div key={title} style={panel}>
                      <div style={{ ...panelHead, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>{title}</span>
                        <span style={{ color: t.muted, fontWeight: 400, fontSize: 11 }}>
                          {count} · {fmt(Math.round(total))}
                          {overdue > 0 && <span style={{ color: "#C00000", marginLeft: 6 }}>· {fmt(Math.round(overdue))} OD</span>}
                        </span>
                      </div>
                      {rows.length === 0
                        ? <div style={{ padding: "16px", color: t.muted, fontSize: 12 }}>No invoices this month.</div>
                        : (
                          <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
                            <table style={{ width: "100%", minWidth: 340, borderCollapse: "collapse" }}>
                              <thead>
                                <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                                  <th style={{ padding: tp, textAlign: "left",  fontWeight: 500 }}>Contact</th>
                                  <th style={{ padding: tp, textAlign: "right", fontWeight: 500, whiteSpace: "nowrap" }}>Amount</th>
                                  <th style={{ padding: tp, textAlign: "right", fontWeight: 500, whiteSpace: "nowrap" }}>Due</th>
                                </tr>
                              </thead>
                              <tbody>
                                {rows.map((inv, i) => {
                                  const od = inv.due_date < new Date().toISOString().slice(0, 10);
                                  return (
                                    <tr key={i} style={{ borderTop: `1px solid ${t.border}`, background: od ? (dark ? "rgba(192,0,0,0.06)" : "rgba(192,0,0,0.04)") : "transparent" }}>
                                      <td style={{ padding: tp, color: od ? "#C00000" : t.text, fontWeight: od ? 600 : 400 }}>{inv.contact_name}</td>
                                      <td style={{ padding: tp, textAlign: "right", whiteSpace: "nowrap" }}>{fmt(inv.amount_due)}</td>
                                      <td style={{ padding: tp, textAlign: "right", color: od ? "#C00000" : t.muted, fontWeight: od ? 600 : 400, whiteSpace: "nowrap" }}>{inv.due_date}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )
                      }
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* ══════════════════════════════════════════
              ALL OWNERS
          ══════════════════════════════════════════ */}
          {!loading && !error && page === "owners" && (
            <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 }}>
              <div style={{ padding: "13px 16px", borderBottom: `1px solid ${t.border}`, color: t.muted, fontSize: 12 }}>
                {allOwners.length} owners · {totalFlagged} flagged · sorted by complex
              </div>
              <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
                <table style={{ width: "100%", minWidth: 480, borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ color: t.muted, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.4px" }}>
                      {["Unit","Owner","Complex","Rent","Bills","Net"].map((h) => (
                        <th key={h} style={{ padding: tp, textAlign: ["Unit","Owner","Complex"].includes(h) ? "left" : "right", fontWeight: 500, whiteSpace: "nowrap" }}>{h}</th>
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
                        <td style={{ padding: tp, color: t.muted, fontFamily: "monospace", fontSize: 12, whiteSpace: "nowrap" }}>{o.code}</td>
                        <td style={{ padding: tp, fontWeight: o.net < 0 ? 600 : 400 }}>{o.name}</td>
                        <td style={{ padding: tp, color: t.muted, fontSize: 12, whiteSpace: "nowrap" }}>{o.complex}</td>
                        <td style={{ padding: tp, textAlign: "right", whiteSpace: "nowrap" }}>{o.rent === 0 ? <span style={{ color: t.danger }}>$0</span> : `$${o.rent.toLocaleString()}`}</td>
                        <td style={{ padding: tp, textAlign: "right", color: t.muted, whiteSpace: "nowrap" }}>${o.bills.toLocaleString()}</td>
                        <td style={{ padding: tp, textAlign: "right", fontWeight: 600, color: o.net < 0 ? t.danger : t.success, whiteSpace: "nowrap" }}>{fmt(o.net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════
              INSPECTIONS
          ══════════════════════════════════════════ */}
          {!loading && !error && page === "inspections" && (() => {
            const card = { background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8 };
            const ph   = { padding: "13px 16px", borderBottom: `1px solid ${t.border}`, fontWeight: 600, fontSize: 13 };

            if (!inspections) {
              return (
                <div style={{ ...card, padding: "32px 24px", color: t.muted, fontSize: 13, textAlign: "center" }}>
                  No inspection data yet — will populate after the next scheduled run.
                </div>
              );
            }

            const summary        = inspections.summary        ?? {};
            const overdue        = inspections.overdue        ?? [];
            const scheduled      = inspections.scheduled      ?? [];
            const freqFlags      = inspections.frequency_flags ?? [];
            const byMgr          = summary.by_manager         ?? {};
            const overdueCount   = summary.total_overdue         ?? 0;
            const scheduledCount = summary.total_scheduled       ?? 0;
            const freqFlagCount  = summary.total_frequency_flags ?? 0;

            const badgeColor = (days) =>
              days > 21 ? "#CC0000" : days > 7 ? "#e07b00" : t.warn;

            return (
              <div>
                {/* ── Stat strip ── */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr 1fr" : "repeat(3,1fr)", gap, marginBottom: gap }}>
                  {[
                    { label: "Overdue",          value: overdueCount,   color: overdueCount   > 0 ? "#CC0000" : t.success },
                    { label: "Scheduled",         value: scheduledCount, color: scheduledCount > 0 ? t.warn    : t.success },
                    { label: "Frequency Flags",  value: freqFlagCount,  color: freqFlagCount  > 0 ? t.warn    : t.success },
                  ].map((s) => (
                    <div key={s.label} style={{ ...card, borderTop: `3px solid ${s.color}`, padding: cp }}>
                      <div style={{ color: t.muted, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 6 }}>{s.label}</div>
                      <div style={{ fontSize: valFz, fontWeight: 700, color: s.color }}>{s.value}</div>
                    </div>
                  ))}
                </div>

                {/* ── Section 1: Overdue + Manager summary ── */}
                <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "3fr 2fr", gap, marginBottom: gap }}>

                  {/* Overdue list */}
                  <div style={card}>
                    <div style={{ ...ph, color: overdueCount > 0 ? "#CC0000" : t.text }}>
                      Overdue — Action Required ({overdueCount})
                    </div>
                    {overdueCount === 0 ? (
                      <div style={{ padding: "20px 16px", display: "flex", alignItems: "center", gap: 10, color: t.success, fontSize: 13 }}>
                        <span style={{ fontSize: 20 }}>✅</span>
                        <span>No properties genuinely overdue</span>
                      </div>
                    ) : (
                      overdue.map((p, i) => {
                        const bc          = badgeColor(p.days_overdue);
                        const borderColor = p.days_overdue > 21 ? "#CC0000" : p.days_overdue > 7 ? "#e07b00" : t.warn;
                        return (
                          <div key={i} style={{
                            borderTop: `1px solid ${t.border}`,
                            borderLeft: `4px solid ${borderColor}`,
                            padding: "11px 14px",
                            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
                          }}>
                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.property}</div>
                              <div style={{ fontSize: 11, color: t.muted, marginTop: 2 }}>
                                {p.manager.split(" ")[0]} · due {p.due_date}
                              </div>
                            </div>
                            <span style={{ background: bc, color: "#fff", fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 12, whiteSpace: "nowrap", flexShrink: 0 }}>
                              {p.days_overdue}d overdue
                            </span>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Manager summary */}
                  <div style={card}>
                    <div style={ph}>Manager Summary</div>
                    <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
                      {Object.entries(byMgr).length === 0 ? (
                        <div style={{ color: t.muted, fontSize: 12 }}>No manager data.</div>
                      ) : (
                        Object.entries(byMgr).map(([mgr, stats]) => {
                          const od  = stats.overdue         ?? 0;
                          const sc  = stats.scheduled       ?? 0;
                          const ff  = stats.frequency_flags ?? 0;
                          const pillBg = od > 0 ? "#CC0000" : (dark ? "#1a3a25" : "#d4edda");
                          const pillTx = od > 0 ? "#fff"    : t.success;
                          return (
                            <div key={mgr}>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                                <span style={{ fontSize: 13, fontWeight: 600 }}>{mgr.split(" ")[0]}</span>
                                <span style={{ background: pillBg, color: pillTx, fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 12, whiteSpace: "nowrap" }}>
                                  {od} overdue
                                </span>
                              </div>
                              <div style={{ display: "flex", gap: 10, fontSize: 11, color: t.muted }}>
                                {sc > 0 && <span style={{ color: t.warn }}>{sc} scheduled</span>}
                                {ff > 0 && <span style={{ color: t.warn }}>{ff} freq flags</span>}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                {/* ── Section 2: Scheduled — no action needed ── */}
                {scheduled.length > 0 && (
                  <div style={{ ...card, marginBottom: gap }}>
                    <div style={{ ...ph, color: t.warn }}>
                      Scheduled — No Action Needed ({scheduledCount})
                    </div>
                    <div style={{ padding: "8px 16px 4px", fontSize: 11, color: t.muted }}>
                      These properties are past their due date but already have a future booking.
                    </div>
                    {scheduled.map((p, i) => (
                      <div key={i} style={{
                        borderTop: `1px solid ${t.border}`,
                        borderLeft: `4px solid ${t.warn}`,
                        padding: "11px 14px",
                        display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
                      }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.property}</div>
                          <div style={{ fontSize: 11, color: t.muted, marginTop: 2 }}>
                            {p.manager.split(" ")[0]} · was due {p.due_date}
                          </div>
                        </div>
                        <span style={{ background: dark ? "rgba(210,153,34,0.15)" : "rgba(154,103,0,0.1)", color: t.warn, fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 12, whiteSpace: "nowrap", flexShrink: 0 }}>
                          Booked {p.booked_date}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* ── Section 3: Frequency flags ── */}
                {freqFlags.length > 0 && (
                  <div style={card}>
                    <div style={{ ...ph, color: t.warn }}>
                      Behind on Inspection Schedule ({freqFlagCount})
                    </div>
                    <div style={{ padding: "8px 16px 4px", fontSize: 11, color: t.muted }}>
                      Properties falling behind the 17-week / 3-per-year inspection cadence.
                    </div>
                    {freqFlags.map((p, i) => (
                      <div key={i} style={{
                        borderTop: `1px solid ${t.border}`,
                        borderLeft: `4px solid ${t.warn}`,
                        padding: "11px 14px",
                        display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
                      }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.property}</div>
                          <div style={{ fontSize: 11, color: t.muted, marginTop: 2 }}>
                            {p.manager.split(" ")[0]} · {p.routine_inspections_done} routine{p.routine_inspections_done !== 1 ? "s" : ""} done · {p.tenancy_months}mo tenancy
                          </div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3, flexShrink: 0 }}>
                          <span style={{ background: dark ? "rgba(210,153,34,0.15)" : "rgba(154,103,0,0.1)", color: t.warn, fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 12, whiteSpace: "nowrap" }}>
                            {p.days_since_last_routine}d since last
                          </span>
                          <span style={{ fontSize: 10, color: t.muted, whiteSpace: "nowrap" }}>{p.flag}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* All-clear if nothing flagged at all */}
                {overdueCount === 0 && scheduledCount === 0 && freqFlagCount === 0 && (
                  <div style={{ ...card, padding: "32px 24px", textAlign: "center", color: t.success, fontSize: 14 }}>
                    ✅ All inspections are on schedule — no flags
                  </div>
                )}
              </div>
            );
          })()}

        </div>
      </div>
    </div>
  );
}
