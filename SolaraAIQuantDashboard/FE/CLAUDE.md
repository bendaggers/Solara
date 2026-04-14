# SolaraAIQuantDashboard

A full-stack forex trade monitoring dashboard built with React (Vite) on the frontend and a to-be-developed backend. Designed to display real-time open trades, history, performance analytics, and backup functionality for the **TI Strategy v2** trading system.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Frontend (FE)](#frontend-fe)
- [Backend (BE)](#backend-be)
- [Pages](#pages)
- [Components](#components)
- [Data Layer](#data-layer)
- [Coding Conventions](#coding-conventions)
- [Design System](#design-system)
- [Roadmap](#roadmap)

---

## Project Overview

**SolaraAIQuantDashboard** is a trade monitoring dashboard for forex traders running automated strategies via MetaTrader. It visualizes open positions, profit/loss in real time, pip calculations, and trade metadata like magic numbers and comments.

The dashboard is inspired by the **Gymove admin dashboard** aesthetic — clean card-based layout, light sidebar, bold typography, and color-coded financial data.

---

## Tech Stack

| Layer     | Technology              |
|-----------|-------------------------|
| Frontend  | React 18 + Vite         |
| Styling   | Plain CSS (per-component files) |
| Fonts     | DM Sans + DM Mono (Google Fonts) |
| Backend   | TBD (Node/Express or Python/FastAPI) |
| Data      | Dummy data (static JS) → will connect to MT5 EA via BE |

---

## Project Structure

```
SolaraAIQuantDashboard/
│
├── FE/                          # Frontend — React dashboard
│   ├── public/
│   ├── src/
│   │   ├── main.jsx             # App entry point — do not modify
│   │   ├── App.jsx              # Root component, handles page routing
│   │   ├── index.css            # Global styles, resets, body font
│   │   │
│   │   ├── data/
│   │   │   └── trades.js        # Dummy trade data + symbol color map
│   │   │
│   │   ├── components/          # Reusable UI components
│   │   │   ├── Sidebar.jsx      # Left navigation sidebar
│   │   │   ├── Sidebar.css
│   │   │   ├── StatCard.jsx     # Summary stat cards (top of Trades page)
│   │   │   ├── StatCard.css
│   │   │   ├── TypeBadge.jsx    # Buy/Sell badge pill
│   │   │   └── TypeBadge.css
│   │   │
│   │   └── pages/               # One file per route/page
│   │       ├── Trades.jsx       # Main open trades table (active page)
│   │       ├── Trades.css
│   │       ├── History.jsx      # Closed trades — Coming Soon
│   │       ├── Performance.jsx  # Analytics — Coming Soon
│   │       ├── BackUp.jsx       # Data export — Coming Soon
│   │       └── DummyPage.css    # Shared styles for Coming Soon pages
│   │
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── BE/                          # Backend — to be developed
```

---

## Getting Started

### Prerequisites

- **Node.js** v20.12.0 or higher (v22.x LTS recommended)
  - Check: `node --version`
  - Download: https://nodejs.org

### Installation

```bash
# 1. Clone or download the project
cd SolaraAIQuantDashboard

# 2. Install frontend dependencies
cd FE
npm install

# 3. Start the dev server
npm run dev
```

### Access the App

Open your browser and go to:
```
http://localhost:5173
```

> Vite auto-picks the next available port (5174, 5175...) if 5173 is busy. Check your terminal output.

### Stop the Server

Press `Ctrl + C` in the terminal.

---

## Frontend (FE)

### Routing

There is **no React Router** installed. Navigation is handled by a simple `useState` in `App.jsx`:

```jsx
const [activePage, setActivePage] = useState("Trades");
```

The `Sidebar` receives `activePage` and `onNavigate` as props. Clicking a nav item calls `onNavigate(label)` which updates the state and renders the matching page component.

**To add a new page:**

1. Create `FE/src/pages/YourPage.jsx`
2. Import it in `App.jsx`
3. Add a `case` in the `renderPage()` switch
4. Add the nav item to the `NAV_ITEMS` array in `Sidebar.jsx`

### Adding a New Component

1. Create `FE/src/components/YourComponent.jsx`
2. Create `FE/src/components/YourComponent.css` alongside it
3. Import the CSS inside the component file: `import "./YourComponent.css"`

---

## Backend (BE)

The `BE/` folder is currently empty and reserved for the backend service. Planned responsibilities:

- Connect to MetaTrader 5 via a bridge (e.g. MT5 Python API or a local socket)
- Expose REST API endpoints for open trades, history, and account info
- Feed real-time data to the React frontend (polling or WebSocket)

**Suggested stack (TBD):**
- Node.js + Express, or
- Python + FastAPI

---

## Pages

| Page        | File                    | Status       | Description                          |
|-------------|-------------------------|--------------|--------------------------------------|
| Trades      | `pages/Trades.jsx`      | ✅ Active    | Open positions table with filtering, column visibility toggle, and row detail modal |
| History     | `pages/History.jsx`     | 🚧 Planned   | Closed trade logs                    |
| Performance | `pages/Performance.jsx` | 🚧 Planned   | Charts, win rate, drawdown analysis  |
| Back Up     | `pages/BackUp.jsx`      | 🚧 Planned   | Export/backup trade data             |

---

## Components

### `Sidebar`
- Props: `activePage` (string), `onNavigate` (function)
- Renders the left navigation with logo, nav items, and account pill
- Light white background with blue active state highlight

### `StatCard`
- Props: `icon`, `label`, `value`, `sub`, `accent` (CSS color string)
- Displays a summary metric card with a colored top border
- Uses CSS custom property `--accent` for the border and icon background tint

### `TypeBadge`
- Props: `type` ("buy" | "sell")
- Renders a green pill for buy, red pill for sell

### `TradeModal`
- File: `src/components/TradeModal.jsx` + `TradeModal.css`
- Props: `trade` (trade object | null), `onClose` (function)
- Opens as a centered overlay when a row is clicked in `Trades.jsx`
- Keyed by `trade.ticket` — always shows the full detail for the selected trade
- Displays **all** trade fields regardless of column visibility state:
  - Header: symbol badge (colored per `SYMBOL_COLORS`), ticket number, open time, type badge
  - P&L hero strip: Floating P&L and Profit in Pips side-by-side
  - Position section: Volume, Entry Price, Market Price
  - Risk Levels section: Stop Loss (red), Take Profit (green)
  - Metadata section: Magic Number, Comment
- Closes on: backdrop click, close button (`×`), or `Escape` key
- Locks body scroll while open

---

## Data Layer

All trade data currently lives in `src/data/trades.js` as a static array:

```js
export const TRADES = [ ... ];
export const SYMBOL_COLORS = { EURUSD: "#3b82f6", ... };
```

**When the backend is ready**, replace the static import in `Trades.jsx` with a `fetch()` or `useEffect` API call. The data shape should match the existing trade object:

```js
{
  ticket:       Number,   // e.g. 1040231
  symbol:       String,   // e.g. "EURUSD"
  time:         String,   // "MM/DD/YYYY HH:MM:SS"
  type:         String,   // "buy" | "sell"
  volume:       Number,   // e.g. 0.10
  entry:        Number,   // e.g. 1.08320
  sl:           Number,   // Stop Loss price
  tp:           Number,   // Take Profit price
  profit:       Number,   // Floating P&L in USD
  currentPrice: Number,   // Current market price
  magic:        Number,   // EA magic number
  comment:      String,   // e.g. "TI V2 LONG"
}
```

### Pip Calculation Logic

Located in `Trades.jsx` as `pipValue()`:

| Symbol type | Multiplier |
|-------------|------------|
| JPY pairs   | × 100      |
| XAU (Gold)  | × 10       |
| All others  | × 10,000   |

---

## Coding Conventions

- **One component per file** — no multiple exports from a single file
- **CSS co-location** — every `.jsx` file has a matching `.css` file in the same folder
- **No inline styles** on new work — use CSS classes instead
- **Fonts** — `DM Sans` for UI text, `DM Mono` for prices and numbers
- **No external UI libraries** — keep the bundle lean, use plain CSS
- **No React Router** (for now) — use the `App.jsx` switch pattern for new pages

---

## Design System

### Colors

| Token         | Value     | Usage                          |
|---------------|-----------|--------------------------------|
| Background    | `#f0f3f8` | Page background                |
| Surface       | `#ffffff` | Cards, sidebar                 |
| Border        | `#e4e9f0` | Dividers, card borders         |
| Text Primary  | `#0f1929` | Headings                       |
| Text Muted    | `#8894a8` | Labels, subtitles              |
| Blue Accent   | `#3b82f6` | Active nav, buttons, links     |
| Green         | `#16a34a` | Profit, TP, buy indicators     |
| Red           | `#dc2626` | Loss, SL, sell indicators      |

### Typography

| Use case      | Font       | Weight |
|---------------|------------|--------|
| Headings      | DM Sans    | 800    |
| Body / Labels | DM Sans    | 400–600|
| Prices / IDs  | DM Mono    | 400–600|

### Stat Card Accents (per card)

| Card          | Accent Color |
|---------------|--------------|
| Total Trades  | `#3b82f6`    |
| Floating P&L  | `#16a34a` / `#dc2626` (dynamic) |
| Win Rate      | `#8b5cf6`    |
| Total Volume  | `#f59e0b`    |

---

## Roadmap

- [ ] Connect `Trades` page to live MT5 data via BE API
- [x] Add column show/hide toggle to `Trades` page (7 default, 6 optional)
- [x] Add trade detail modal on row click (all fields, keyed by ticket number)
- [ ] Build `History` page with closed trade logs and date filtering
- [ ] Build `Performance` page with equity curve chart and key metrics
- [ ] Build `Back Up` page with CSV/JSON export
- [ ] Add WebSocket support for real-time price updates
- [ ] Add authentication (login screen)
- [ ] Mobile-responsive layout

---

## Author

**TI Strategy v2** — Solara Quant Systems  
Dashboard inspired by [Gymove React Vite Admin Template](https://gymove-vite.vercel.app/)
