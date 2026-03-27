/**
 * Parse an API timestamp as UTC.
 *
 * The backend stores datetimes in UTC but SQLite strips timezone info,
 * so the API returns naive ISO strings like "2026-03-27T12:00:00".
 * Without a trailing "Z", JavaScript's Date constructor treats these as
 * local time. This helper appends "Z" when no timezone indicator is present.
 */
export function utc(ts: string): Date {
  if (!ts) return new Date();
  const s = ts.trim();
  if (/[Zz]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  return new Date(s + 'Z');
}
