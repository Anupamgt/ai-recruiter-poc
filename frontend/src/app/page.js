import Link from "next/link";

const FEATURES = [
  {
    icon: "🧠",
    title: "Deep Understanding",
    description:
      "Our AI reads every CV in full — parsing skills, experience, education, and nuanced context that keyword filters miss.",
  },
  {
    icon: "🎯",
    title: "Contextual Relevance",
    description:
      "Candidates are ranked by true fit, not surface matches. The system understands that 'React Native' experience is relevant to a 'Mobile Engineer' role.",
  },
  {
    icon: "📊",
    title: "Signal Integration",
    description:
      "Your thumbs-up and thumbs-down feedback is fed back to the model, continuously sharpening future shortlists to your taste.",
  },
];

const STATS = [
  { value: "< 30s", label: "Time to shortlist" },
  { value: "95%", label: "Relevance accuracy" },
  { value: "10×", label: "Faster than manual" },
];

export default function HomePage() {
  return (
    <div className="page-content">
      <div className="container">
        {/* ── Hero ── */}
        <section className="hero animate-fade-in">
          <h1 style={{ fontFamily: "var(--font-outfit), sans-serif" }}>
            AI-Powered
            <br />
            Recruiting
          </h1>

          <p className="hero-subtitle">
            Upload a job description, and our AI will deeply analyze every
            candidate — returning a ranked shortlist with transparent scoring in
            seconds, not hours.
          </p>

          <div className="hero-actions">
            <Link href="/upload-jd" className="btn btn-primary">
              🚀&nbsp;&nbsp;Start a Search
            </Link>
            <Link href="#features" className="btn btn-ghost">
              Learn More&nbsp;&nbsp;↓
            </Link>
          </div>
        </section>

        {/* ── Feature pillars ── */}
        <section id="features" className="features-grid">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="glass-card feature-card animate-slide-up"
              style={{ animationDelay: `${i * 120}ms`, animationFillMode: "both" }}
            >
              <span className="feature-icon" aria-hidden="true">
                {f.icon}
              </span>
              <h3 style={{ fontFamily: "var(--font-outfit), sans-serif" }}>
                {f.title}
              </h3>
              <p>{f.description}</p>
            </div>
          ))}
        </section>

        {/* ── Stats ── */}
        <section className="stats-row animate-fade-in" style={{ animationDelay: "400ms", animationFillMode: "both" }}>
          {STATS.map((s) => (
            <div key={s.label} className="stat">
              <div
                className="stat-value"
                style={{ fontFamily: "var(--font-outfit), sans-serif" }}
              >
                {s.value}
              </div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
