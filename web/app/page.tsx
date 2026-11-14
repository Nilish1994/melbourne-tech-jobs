import Link from "next/link";
import { api, type Locations, type Salaries, type SkillGroup, type Skills, type Summary } from "@/lib/api";
import { dateTime, number } from "@/lib/format";
import { Card, Stat } from "@/components/Card";
import { LocationList } from "@/components/LocationList";
import { SalaryRanges } from "@/components/SalaryRanges";
import { SkillsPanel } from "@/components/SkillsPanel";
import { TrendPanel } from "@/components/TrendPanel";

export const dynamic = "force-dynamic";

const DAYS = 30;

export default async function Dashboard() {
  let data;
  try {
    data = await Promise.all([
      api<Summary>(`/analytics/summary?days=${DAYS}`),
      api<Skills>(`/analytics/skills?days=${DAYS}&limit=15`),
      api<SkillGroup[]>("/analytics/skills/groups", 3600),
      api<Salaries>("/analytics/salaries?days=90&min_jobs=5&limit=12"),
      api<Locations>(`/analytics/locations?days=${DAYS}&limit=10`),
    ]);
  } catch {
    return (
      <div className="rounded-xl border border-line bg-surface p-8 text-center">
        <h1 className="text-lg font-semibold">The data service is unavailable</h1>
        <p className="mt-1 text-sm text-muted">Please try again in a minute.</p>
      </div>
    );
  }
  const [summary, skills, groups, salaries, locations] = data;
  const trendOptions = skills.items.slice(0, 10).map((s) => s.skill);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">What Melbourne&apos;s tech employers are hiring for</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Every IT job advertised in Melbourne on Adzuna, collected daily. Skills are matched in each job&apos;s
          title and description, then counted, priced and mapped. Last updated {dateTime(summary.last_updated)}.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={`Tech jobs, last ${DAYS} days`} value={number(summary.jobs)} hint={`${number(summary.jobs_last_7_days)} in the last week`} />
        <Stat label="Hiring companies" value={number(summary.companies)} />
        <Stat label="Most requested skill" value={summary.top_skill?.skill ?? "—"}
          hint={summary.top_skill ? `${number(summary.top_skill.jobs)} jobs` : undefined} />
        <Stat label="Jobs with a salary" value={summary.salary_coverage_pct === null ? "—" : `${summary.salary_coverage_pct}%`}
          hint="advertised annual range" />
      </div>

      <Card title="Most requested skills" subtitle={`Share of tech jobs mentioning each skill, last ${DAYS} days, and the change from the ${DAYS} days before.`}>
        <SkillsPanel initial={skills} groups={groups} />
      </Card>

      <Card title="Skill demand over time" subtitle="Weekly share of tech jobs mentioning each skill, last 12 weeks.">
        <TrendPanel options={trendOptions} initialSelected={trendOptions.slice(0, 3)} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card title="What skills pay" subtitle="Advertised annual salary by skill, last 90 days, sorted by median.">
          <SalaryRanges data={salaries} />
        </Card>
        <Card title="Where the jobs are" subtitle={`Top areas, last ${DAYS} days.`}>
          <LocationList data={locations} />
          <Link href="/jobs" className="mt-6 inline-block text-sm text-accent hover:underline">Browse the latest jobs →</Link>
        </Card>
      </div>
    </div>
  );
}
