"use client";

import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SkillGroup, SkillRow, Skills } from "@/lib/api";
import { Empty } from "./Card";

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">new</span>;
  if (Math.abs(value) < 0.5) return <span className="text-muted">±0</span>;
  return (
    <span className={value > 0 ? "text-up" : "text-down"}>
      {value > 0 ? "▲" : "▼"} {Math.abs(value).toFixed(1)} pts
    </span>
  );
}

export function SkillsPanel({ initial, groups }: { initial: Skills; groups: SkillGroup[] }) {
  const [group, setGroup] = useState<string | null>(null);
  const [data, setData] = useState<Skills>(initial);
  const [loading, setLoading] = useState(false);

  async function choose(next: string | null) {
    setGroup(next);
    if (next === null) return setData(initial);
    setLoading(true);
    try {
      const response = await fetch(`/api/analytics/skills?days=${initial.days}&limit=15&group=${encodeURIComponent(next)}`);
      if (response.ok) setData(await response.json());
    } finally {
      setLoading(false);
    }
  }

  const rows: SkillRow[] = data.items.slice(0, 15);
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1.5" role="tablist" aria-label="Skill group">
        {[null, ...groups.map((g) => g.group)].map((name) => (
          <button
            key={name ?? "all"}
            role="tab"
            aria-selected={group === name}
            onClick={() => choose(name)}
            className={`rounded-full border px-3 py-1 text-xs ${
              group === name ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-ink"
            }`}
          >
            {name ?? "All skills"}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty>No jobs mention these skills in the last {data.days} days.</Empty>
      ) : (
        <div className={`grid gap-6 lg:grid-cols-[1fr_260px] ${loading ? "opacity-60" : ""}`}>
          <div className="h-[420px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
                <XAxis type="number" unit="%" tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--line)" />
                <YAxis type="category" dataKey="skill" width={120} tick={{ fill: "var(--ink)", fontSize: 12 }} stroke="var(--line)" />
                <Tooltip
                  cursor={{ fill: "var(--accent-soft)" }}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8 }}
                  formatter={(value: number, _name, item) => [`${value}% of jobs (${item.payload.jobs})`, "Share"]}
                />
                <Bar dataKey="share_pct" fill="var(--chart-1)" radius={[0, 4, 4, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="h-fit w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="pb-2 font-normal">Skill</th>
                <th className="pb-2 text-right font-normal">vs previous {data.days}d</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 10).map((row) => (
                <tr key={row.skill} className="border-t border-line">
                  <td className="py-1.5">{row.skill}</td>
                  <td className="py-1.5 text-right tabular-nums"><Change value={row.share_change_pts} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
