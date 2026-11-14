import Link from "next/link";
import { api, type JobPage, type SkillGroup } from "@/lib/api";
import { date, number, salaryRange } from "@/lib/format";
import { Empty } from "@/components/Card";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

type Search = { search?: string; skill?: string; location?: string; page?: string };

function pageHref(params: Search, page: number) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...params, page: String(page) })) if (value) query.set(key, value);
  return `/jobs?${query}`;
}

export default async function Jobs({ searchParams }: { searchParams: Promise<Search> }) {
  const params = await searchParams;
  const page = Math.max(1, Number.parseInt(params.page ?? "1", 10) || 1);
  const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (params.search?.trim()) query.set("search", params.search.trim().slice(0, 200));
  if (params.skill) query.set("skill", params.skill);
  if (params.location?.trim()) query.set("location", params.location.trim().slice(0, 200));

  let jobs: JobPage | null = null;
  let groups: SkillGroup[] = [];
  try {
    [jobs, groups] = await Promise.all([
      api<JobPage>(`/jobs?${query}`, 120),
      api<SkillGroup[]>("/analytics/skills/groups", 3600),
    ]);
  } catch {
    jobs = null;
  }
  const pages = jobs ? Math.max(1, Math.ceil(jobs.total / PAGE_SIZE)) : 1;
  const input = "rounded-lg border border-line bg-surface px-3 py-2 text-sm";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Latest Melbourne tech jobs</h1>
        <p className="mt-1 text-sm text-muted">Newest first. Each listing opens the original advert on Adzuna.</p>
      </div>

      <form className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]" action="/jobs">
        <input name="search" defaultValue={params.search} placeholder="Title or keyword" aria-label="Keyword" className={input} />
        <select name="skill" defaultValue={params.skill ?? ""} aria-label="Skill" className={input}>
          <option value="">Any skill</option>
          {groups.map((group) => (
            <optgroup key={group.group} label={group.group}>
              {group.skills.map((skill) => <option key={skill} value={skill}>{skill}</option>)}
            </optgroup>
          ))}
        </select>
        <input name="location" defaultValue={params.location} placeholder="Suburb" aria-label="Suburb" className={input} />
        <button className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white dark:text-black">Search</button>
      </form>

      {!jobs ? (
        <Empty>The data service is unavailable. Please try again in a minute.</Empty>
      ) : jobs.items.length === 0 ? (
        <Empty>No jobs match. Try fewer filters.</Empty>
      ) : (
        <>
          <p className="text-sm text-muted">{number(jobs.total)} jobs</p>
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {jobs.items.map((job) => (
              <li key={job.id} className="p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  {job.source_url ? (
                    <a href={job.source_url} rel="nofollow noopener" target="_blank" className="font-medium hover:text-accent hover:underline">
                      {job.title}
                    </a>
                  ) : (
                    <span className="font-medium">{job.title}</span>
                  )}
                  <span className="text-sm tabular-nums text-muted">{date(job.posted_at ?? job.first_seen_at)}</span>
                </div>
                <div className="mt-0.5 text-sm text-muted">
                  {[job.company_name, job.location, salaryRange(job.salary_min, job.salary_max)].filter(Boolean).join(" · ")}
                </div>
                {job.skills.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {job.skills.map((skill) => (
                      <Link key={skill} href={`/jobs?skill=${encodeURIComponent(skill)}`}
                        className="rounded bg-accent-soft px-1.5 py-0.5 text-xs text-accent hover:underline">
                        {skill}
                      </Link>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
          <nav className="flex items-center justify-between text-sm" aria-label="Pagination">
            {page > 1 ? <Link href={pageHref(params, page - 1)} className="text-accent hover:underline">← Newer</Link> : <span />}
            <span className="text-muted">Page {page} of {number(pages)}</span>
            {page < pages ? <Link href={pageHref(params, page + 1)} className="text-accent hover:underline">Older →</Link> : <span />}
          </nav>
        </>
      )}
      <p className="text-xs text-muted">
        <a href="https://www.adzuna.com.au" className="underline">Jobs by Adzuna</a>
      </p>
    </div>
  );
}
