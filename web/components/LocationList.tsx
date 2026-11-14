import type { Locations } from "@/lib/api";
import { number } from "@/lib/format";
import { Empty } from "./Card";

export function LocationList({ data }: { data: Locations }) {
  if (data.items.length === 0) return <Empty>No locations yet.</Empty>;
  const max = Math.max(...data.items.map((item) => item.jobs));
  return (
    <ul className="space-y-2">
      {data.items.map((item) => (
        <li key={item.area} className="text-sm">
          <div className="flex justify-between">
            <span>{item.area}</span>
            <span className="tabular-nums text-muted">{number(item.jobs)} · {item.share_pct}%</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-line">
            <div className="h-1.5 rounded-full bg-accent" style={{ width: `${(item.jobs / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
