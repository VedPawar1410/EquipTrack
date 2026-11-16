const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const relFmt = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatDate(value?: string | null) {
  return value ? dateFmt.format(new Date(value)) : "—";
}

/** "2 days ago", "in 5 days". Only call from data-dependent rendering (in the browser), never at prerender. */
export function relativeTime(value: string) {
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000);
  if (Math.abs(days) < 1) {
    const hours = Math.round((new Date(value).getTime() - Date.now()) / 3_600_000);
    return Math.abs(hours) < 1 ? "just now" : relFmt.format(hours, "hour");
  }
  return relFmt.format(days, "day");
}

export function currency(value?: number | null) {
  return value == null ? "—" : value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}
