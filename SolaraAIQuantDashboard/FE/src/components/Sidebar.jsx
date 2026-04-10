import "./Sidebar.css";

const NAV_ITEMS = [
  { icon: "💹", label: "Trades"      },
  { icon: "📁", label: "History"     },
  { icon: "📊", label: "Performance" },
  { icon: "💾", label: "Back Up"     },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">⚡</div>
        <div>
          <div className="sidebar-logo-title">Solara AI Quant</div>
          <div className="sidebar-logo-sub">Dashboard</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="sidebar-nav-label">Menu</div>
        {NAV_ITEMS.map((item) => (
          <div
            key={item.label}
            className={`sidebar-nav-item ${activePage === item.label ? "active" : ""}`}
            onClick={() => onNavigate(item.label)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
      </nav>

      {/* Account Pill */}
      <div className="sidebar-account">
        <div className="sidebar-account-pill">
          <div className="sidebar-account-avatar">FX</div>
          <div>
            <div className="sidebar-account-name">TI Strategy v2</div>
            <div className="sidebar-account-status">
              <span className="status-dot" />
              Live Account
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
