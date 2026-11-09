const P = {
  dash: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z", megaphone: "M3 11v2a1 1 0 0 0 1 1h3l8 4V6L7 10H4a1 1 0 0 0-1 1zM18 9a4 4 0 0 1 0 6", pen: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  bot: "M5 8h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2zM12 8V4M9 14h.01M15 14h.01", cal: "M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14H3zM3 10h18M8 2v4M16 2v4",
  check: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM8 12l3 3 5-6", send: "M22 2 11 13M22 2l-7 20-4-9-9-4z", chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  plug: "M9 2v6M15 2v6M7 8h10v4a5 5 0 0 1-10 0zM12 17v5", users: "M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM21 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4", mic: "M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zM19 11a7 7 0 0 1-14 0M12 18v4",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9zM13.7 21a2 2 0 0 1-3.4 0", search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3", sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z", plus: "M12 5v14M5 12h14", spark: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  cam: "M23 7l-7 5 7 5zM1 5h15v14H1z", hand: "M18 11V6a2 2 0 0 0-4 0M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8M18 8a2 2 0 0 1 4 0v6a8 8 0 0 1-8 8h-2a8 8 0 0 1-6-2.7L3 16a2 2 0 0 1 3-2.7L8 15",
  face: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01", pal: "M12 22a10 10 0 1 1 10-10c0 2.2-2 3-4 3h-2a2 2 0 0 0-1.4 3.4A2 2 0 0 1 12 22zM7.5 11h.01M10 7h.01M15 7h.01M17.5 11h.01",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4", file: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5", list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01", crown: "M2 8l5 4 5-8 5 8 5-4-2 11H4z",
  play: "M5 3l14 9-14 9z", help: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01", menu: "M4 6h16M4 12h16M4 18h16",
};
export default function Icon({ n, className = "ic" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={P[n] || P.dash} /></svg>;
}

// An original illustration (not a photo or a render): a robotic head with an emerald glow.
export function RobotArt() {
  return (
    <svg viewBox="0 0 360 240" role="img" aria-label="Illustration of an AI agent" style={{ color: "var(--pri)" }}>
      <defs>
        <radialGradient id="g1" cx="50%" cy="48%" r="55%"><stop offset="0" stopColor="currentColor" stopOpacity=".42" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></radialGradient>
        <linearGradient id="g2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#14241d" /><stop offset="1" stopColor="#060e0b" /></linearGradient>
      </defs>
      <circle cx="180" cy="122" r="112" fill="url(#g1)" />
      <g fill="none" stroke="currentColor" strokeOpacity=".5"><circle cx="180" cy="122" r="96" strokeDasharray="3 7" /><circle cx="180" cy="122" r="76" strokeOpacity=".3" /></g>
      <path d="M180 30v26" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /><circle cx="180" cy="26" r="6" fill="currentColor" />
      <rect x="120" y="58" width="120" height="110" rx="30" fill="url(#g2)" stroke="currentColor" strokeOpacity=".9" strokeWidth="2" />
      <rect x="138" y="92" width="84" height="34" rx="17" fill="#02100a" stroke="currentColor" strokeOpacity=".7" />
      <circle cx="162" cy="109" r="8" fill="currentColor" /><circle cx="198" cy="109" r="8" fill="currentColor" />
      <circle cx="162" cy="109" r="14" fill="none" stroke="currentColor" strokeOpacity=".35" /><circle cx="198" cy="109" r="14" fill="none" stroke="currentColor" strokeOpacity=".35" />
      <path d="M158 148h44" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeOpacity=".8" /><path d="M170 156h20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeOpacity=".5" />
      <rect x="106" y="96" width="10" height="40" rx="5" fill="currentColor" fillOpacity=".7" /><rect x="244" y="96" width="10" height="40" rx="5" fill="currentColor" fillOpacity=".7" />
      <path d="M140 176q40 26 80 0" fill="none" stroke="currentColor" strokeOpacity=".5" strokeWidth="2" />
      <g fill="currentColor" fillOpacity=".7"><circle cx="64" cy="70" r="2" /><circle cx="92" cy="40" r="1.5" /><circle cx="300" cy="60" r="2" /><circle cx="322" cy="120" r="1.5" /><circle cx="48" cy="150" r="1.5" /><circle cx="290" cy="188" r="2" /></g>
    </svg>
  );
}
