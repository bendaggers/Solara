import "./TypeBadge.css";

export default function TypeBadge({ type }) {
  return (
    <span className={`type-badge ${type}`}>
      {type === "buy" ? "▲" : "▼"} {type}
    </span>
  );
}
