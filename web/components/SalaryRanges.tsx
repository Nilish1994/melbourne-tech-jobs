import type { SalaryRow, Salaries } from "@/lib/api";
import { money } from "@/lib/format";
import { Empty } from "./Card";

// Range bars drawn with CSS: the shaded band is the middle 50% (p25–p75) and the
// tick is the median, on one shared scale so rows are comparable.
export function SalaryRanges({ data }: { data: Salaries }) {
  const rows: SalaryRow[] = [...(data.overall ? [data.overall] : []), ...data.items].filter(
    (row) => row.p25 !== null && row.p75 !== null && row.median !== null,
  );
  if (rows.length === 0) return <Empty>Not enough advertised salaries yet.</Empty>;
  const low = Math.min(...rows.map((r) => r.p25!));
  const high = Math.max(...rows.map((r) => r.p75!));
  const span = Math.max(high - low, 1);
  const at = (value: number) => `${((value - low) / span) * 100}%`;

  return (
    <div>
      <ul className="space-y-2.5">
        {rows.map((row, index) => (
          <li key={row.skill} className="grid grid-cols-[120px_1fr_64px] items-center gap-3 text-sm">
            <span className={index === 0 && data.overall ? "font-medium" : ""}>{row.skill}</span>
            <div className="relative h-5" role="img"
              aria-label={`${row.skill}: middle 50% ${money(row.p25)} to ${money(row.p75)}, median ${money(row.median)}`}>
              <div className="absolute inset-y-2 left-0 right-0 rounded-full bg-line" />
              <div className="absolute inset-y-1 rounded-full bg-accent-soft"
                style={{ left: at(row.p25!), width: `calc(${at(row.p75!)} - ${at(row.p25!)})` }} />
              <div className="absolute inset-y-0 w-0.5 rounded bg-accent" style={{ left: at(row.median!) }} />
            </div>
            <span className="text-right tabular-nums">{money(row.median)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">
        Band: middle 50% of advertised salaries · line: median · {data.note} Skills need at least 5 jobs with a salary.
      </p>
    </div>
  );
}
