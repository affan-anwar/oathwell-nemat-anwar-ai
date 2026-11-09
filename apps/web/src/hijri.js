// Pure date arithmetic. No schedule data is invented here.
export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const HIJRI = ["Muharram", "Safar", "Rabi’ al-Awwal", "Rabi’ al-Thani", "Jumada al-Awwal", "Jumada al-Thani", "Rajab", "Sha’ban", "Ramadan", "Shawwal", "Dhu al-Qi’dah", "Dhu al-Hijjah"];
export const OCCASIONS = { "1-1": "Islamic New Year", "1-10": "Ashura", "3-12": "Mawlid (12 Rabi’ al-Awwal)", "9-1": "Ramadan begins", "10-1": "Eid al-Fitr", "12-9": "Day of Arafah", "12-10": "Eid al-Adha" };
const fmt = new Intl.DateTimeFormat("en-u-ca-islamic-civil-nu-latn", { day: "numeric", month: "numeric", year: "numeric", timeZone: "UTC" });

export function utc(y, m, d) {
  const t = new Date(0);
  t.setUTCFullYear(y, m, d);
  t.setUTCHours(12, 0, 0, 0);
  return t;
}
export const daysIn = (y, m) => utc(y, m + 1, 0).getUTCDate();

// Tabular Islamic calendar. It can differ by one day from moon sighting. Not defined before 1 AH (622 CE).
export function hijriOf(y, m, d) {
  if (y < 622 || (y === 622 && (m < 6 || (m === 6 && d < 19)))) return null;
  const o = {};
  fmt.formatToParts(utc(y, m, d)).forEach((p) => { o[p.type] = Number(p.value); });
  return o.year > 0 ? { d: o.day, m: o.month, y: o.year } : null;
}

export function monthCells(y, m) {
  const cells = [];
  for (let i = 0; i < utc(y, m, 1).getUTCDay(); i++) cells.push(null);
  for (let d = 1; d <= daysIn(y, m); d++) {
    const h = hijriOf(y, m, d);
    cells.push({ d, h, occasion: h ? OCCASIONS[`${h.m}-${h.d}`] : null });
  }
  return cells;
}
