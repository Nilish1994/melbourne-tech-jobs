export const number = (value: number) => new Intl.NumberFormat("en-AU").format(value);

export const money = (value: number | string | null | undefined) => {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0) return null;
  return amount >= 1000 ? `$${Math.round(amount / 1000)}k` : `$${Math.round(amount)}`;
};

export const salaryRange = (min: string | null, max: string | null) => {
  const low = money(min);
  const high = money(max);
  if (low && high && low !== high) return `${low}–${high}`;
  return low ?? high;
};

export const date = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", timeZone: "Australia/Melbourne" }).format(new Date(value))
    : "—";

export const dateTime = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-AU", {
        day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Australia/Melbourne",
      }).format(new Date(value))
    : "not yet";
