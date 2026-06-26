import { Inter, Outfit } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

export const metadata = {
  title: "AI Recruiter — Intelligent Candidate Shortlisting",
  description:
    "Upload a job description, let AI deeply understand each candidate, and get a ranked shortlist in seconds.",
};

import LatencyCounter from "./components/LatencyCounter";

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${inter.variable} ${outfit.variable}`}>
      <body style={{ fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
        {/* ── Ambient background orbs ── */}
        <div className="bg-orbs" aria-hidden="true">
          <div className="orb orb-1" />
          <div className="orb orb-2" />
          <div className="orb orb-3" />
        </div>

        {/* ── Top accent gradient line ── */}
        <div className="accent-line" aria-hidden="true" />

        {/* ── Navigation ── */}
        <nav className="nav">
          <div className="nav-inner">
            <Link
              href="/"
              className="nav-logo"
              style={{ fontFamily: "var(--font-outfit), sans-serif" }}
            >
              ◆ AI Recruiter
            </Link>

            <ul className="nav-links">
              <li>
                <Link href="/">Home</Link>
              </li>
              <li>
                <Link href="/upload-jd">New Search</Link>
              </li>
            </ul>
          </div>
        </nav>

        {/* ── Page content ── */}
        <main>{children}</main>
        <LatencyCounter />
      </body>
    </html>
  );
}
