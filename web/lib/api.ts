// Server-side access to the FastAPI service. The browser never talks to the API
// directly: client components go through the /api route handler, which only
// forwards read-only analytics and job requests.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, revalidate = 300): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { next: { revalidate } });
  if (!response.ok) throw new ApiError(response.status, `API ${response.status} for ${path}`);
  return response.json() as Promise<T>;
}

export type Summary = {
  days: number;
  jobs: number;
  companies: number;
  salary_coverage_pct: number | null;
  jobs_last_7_days: number;
  total_jobs_stored: number;
  top_skill: { skill: string; jobs: number } | null;
  last_updated: string | null;
};

export type SkillRow = {
  skill: string;
  group: string | null;
  jobs: number;
  share_pct: number;
  previous_jobs: number;
  share_change_pts: number | null;
};
export type Skills = { days: number; total_jobs: number; items: SkillRow[] };
export type SkillGroup = { group: string; skills: string[] };

export type TrendPoint = { week: string; total_jobs: number } & Record<string, number | string | null>;
export type Trend = { skills: string[]; weeks: number; points: TrendPoint[] };

export type SalaryRow = { skill: string; jobs: number; p25: number | null; median: number | null; p75: number | null };
export type Salaries = { days: number; overall: SalaryRow | null; items: SalaryRow[]; note: string };

export type Locations = { days: number; total_jobs: number; items: { area: string; jobs: number; share_pct: number }[] };

export type Job = {
  id: string;
  title: string;
  company_name: string | null;
  location: string | null;
  salary_min: string | null;
  salary_max: string | null;
  employment_type: string | null;
  source_url: string | null;
  posted_at: string | null;
  first_seen_at: string;
  skills: string[];
};
export type JobPage = { items: Job[]; total: number; page: number; page_size: number };
