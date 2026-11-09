import { useRef, useState } from "react";

// A small accessible line chart. Values come from the API; nothing is generated here.
export default function Chart({ data, lines, label }) {
  const [hover, setHover] = useState(null);
  const box = useRef(null);
  const W = 640, H = 230, L = 40, R = 12, T = 12, B = 28;
  const max = Math.max(4, ...data.flatMap((d) => lines.map((l) => d[l.key] || 0)));
  const top = Math.ceil(max / 4) * 4;
  const x = (i) => L + (data.length === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (data.length - 1));
  const y = (v) => T + (H - T - B) * (1 - v / top);
  const move = (e) => {
    const r = box.current.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(data.length - 1, Math.round(((px - L) / (W - L - R)) * (data.length - 1)))));
  };
  const step = Math.max(1, Math.ceil(data.length / 7));
  return (
    <div className="chart chartwrap" ref={box} onMouseMove={move} onMouseLeave={() => setHover(null)}>
      <div className="legend">{lines.map((l) => <span key={l.key}><i style={{ background: l.color }} />{l.label}</span>)}</div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {[0, 1, 2, 3, 4].map((g) => { const v = (top * g) / 4; return <g key={g}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--ln)" /><text x={L - 6} y={y(v) + 4} textAnchor="end">{Math.round(v)}</text></g>; })}
        {data.map((d, i) => (i % step === 0 || i === data.length - 1) && <text key={d.date} x={x(i)} y={H - 8} textAnchor={i === data.length - 1 ? "end" : i === 0 ? "start" : "middle"}>{d.date.slice(5)}</text>)}
        {lines.map((l) => <g key={l.key}>
          <polyline fill="none" stroke={l.color} strokeWidth="2.5" strokeLinejoin="round" points={data.map((d, i) => `${x(i)},${y(d[l.key] || 0)}`).join(" ")} />
          {data.map((d, i) => <circle key={i} cx={x(i)} cy={y(d[l.key] || 0)} r={hover === i ? 5 : 3} fill="var(--sf)" stroke={l.color} strokeWidth="2" />)}
        </g>)}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="var(--mu)" strokeDasharray="4 4" />}
      </svg>
      {hover !== null && <div className="tip" style={{ left: `${Math.min(70, (x(hover) / W) * 100)}%`, top: 28 }}>
        <b>{data[hover].date}</b>{lines.map((l) => <div key={l.key}>{l.label}: {data[hover][l.key] || 0}</div>)}</div>}
      <div className="sr-only"><table><caption>{label}</caption><thead><tr><th>Date</th>{lines.map((l) => <th key={l.key}>{l.label}</th>)}</tr></thead>
        <tbody>{data.map((d) => <tr key={d.date}><td>{d.date}</td>{lines.map((l) => <td key={l.key}>{d[l.key] || 0}</td>)}</tr>)}</tbody></table></div>
    </div>
  );
}
