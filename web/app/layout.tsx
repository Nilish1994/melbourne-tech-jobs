import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Melbourne Tech Jobs",
  description: "Which tech skills Melbourne employers are hiring for, what they pay, and where — updated daily from Adzuna.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="border-b border-line bg-surface">
          <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              Melbourne Tech Jobs
            </Link>
            <div className="flex gap-4 text-sm text-muted">
              <Link href="/" className="hover:text-ink">Dashboard</Link>
              <Link href="/jobs" className="hover:text-ink">Jobs</Link>
              <a href="https://github.com/Nilish1994/melbourne-tech-jobs" className="hover:text-ink">GitHub</a>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-muted">
          <p>
            Job data:{" "}
            <a href="https://www.adzuna.com.au" className="underline hover:text-ink">Jobs by Adzuna</a>
            . Skills are matched from job titles and Adzuna&apos;s description snippets, so counts are indicative.
            Built by Nilish Aluthwatta.
          </p>
        </footer>
      </body>
    </html>
  );
}
