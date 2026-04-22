import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Trades from "./pages/Trades";
import History from "./pages/History";
import Performance from "./pages/Performance";
import BackUp from "./pages/BackUp";
import "./index.css";

export default function App() {
  const [activePage, setActivePage] = useState("Trades");

  const renderPage = () => {
    switch (activePage) {
      case "Trades":      return <Trades />;
      case "History":     return <History />;
      case "Performance": return <Performance />;
      case "Back Up":     return <BackUp />;
      default:            return <Trades />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="app-main">
        {renderPage()}
      </main>
    </div>
  );
}
