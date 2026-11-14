"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Trend } from "@/lib/api";
import { Empty } from "./Card";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const MAX_SELECTED = 5;

export function TrendPanel({ options, initialSelected }: { options: string[]; initialSelected: string[] }) {
  const [selected, setSelected] = useState(initialSelected);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (selected.length === 0) return;
    const query = selected.map((s) => `skill=${encodeURIComponent(s)}`).join("&");
    let cancelled = false;
    fetch(`/api/analytics/skills/trend?weeks=12&${query}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: Trend) => !cancelled && (setTrend(data), setError(false)))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  function toggle(skill: string) {
    setSelected((current) =>
      current.includes(skill)
        ? current.filter((s) => s !== skill)
        : current.length >= MAX_SELECTED ? current : [...current, skill],
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {options.map((skill) => {
          const index = selected.indexOf(skill);
          return (
            <button
              key={skill}
              onClick={() => toggle(skill)}
              aria-pressed={index >= 0}
              className={`rounded-full border px-3 py-1 text-xs ${index >= 0 ? "text-ink" : "border-line text-muted hover:text-ink"}`}
              style={index >= 0 ? { borderColor: COLORS[index] } : undefined}
            >
              {index >= 0 && <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: COLORS[index] }} />}
              {skill}
            </button>
          );
        })}
      </div>
      {selected.length === 0 ? (
        <Empty>Pick up to {MAX_SELECTED} skills to compare.</Empty>
      ) : error ? (
        <Empty>Couldn&apos;t load the trend. Try again shortly.</Empty>
      ) : !trend || trend.points.length < 2 ? (
        <Empty>{trend ? "Not enough weeks of data yet — check back soon." : "Loading…"}</Empty>
      ) : (
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend.points} margin={{ left: 0, right: 16, top: 8 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="week" tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--line)"
                tickFormatter={(w: string) => new Date(w).toLocaleDateString("en-AU", { day: "numeric", month: "short" })} />
              <YAxis unit="%" tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--line)" width={44} />
              <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8 }}
                formatter={(value: number) => `${value}% of jobs`} labelFormatter={(w: string) => `Week of ${w}`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {trend.skills.map((skill) => (
                <Line key={skill} type="monotone" dataKey={skill} stroke={COLORS[selected.indexOf(skill)] ?? COLORS[0]}
                  strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
