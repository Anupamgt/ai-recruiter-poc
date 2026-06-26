'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import CandidateCard from '../../components/CandidateCard';
import StageIndicator from '../../components/StageIndicator';

export default function ShortlistPage() {
  const params = useParams();
  const router = useRouter();
  const jdId = params?.jdId;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stage, setStage] = useState("A");
  const [stageBCount, setStageBCount] = useState(0);

  useEffect(() => {
    if (!jdId) return;

    setLoading(true);
    setError(null);
    setStage("A");
    setStageBCount(0);

    const es = new EventSource(`http://localhost:8000/jd/${jdId}/shortlist/stream`);

    es.addEventListener("stage_a", (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setData(parsed);
        setLoading(false);
      } catch (err) {
        setError("Failed to parse Stage A stream data");
        setLoading(false);
      }
    });

    es.addEventListener("stage_b", (e) => {
      try {
        const item = JSON.parse(e.data);
        setStage("B");
        setStageBCount((prev) => prev + 1);
        setData((prev) => {
          if (!prev || !prev.candidates) return prev;
          const updatedCandidates = prev.candidates.map((c) => {
            if (c.candidate_id === item.candidate_id) {
              return { ...c, ...item };
            }
            return c;
          });
          // Re-sort candidates by Stage B fit_score descending (falling back to Stage A score)
          updatedCandidates.sort((a, b) => {
            const sA = a.fit_score !== undefined ? a.fit_score : a.stage_a_score * 100;
            const sB = b.fit_score !== undefined ? b.fit_score : b.stage_a_score * 100;
            return sB - sA;
          });
          // Re-assign ranks
          const ranked = updatedCandidates.map((c, idx) => ({ ...c, rank: idx + 1 }));
          return { ...prev, stage: "B", candidates: ranked };
        });
      } catch (err) {
        console.error("Error updating Stage B candidate:", err);
      }
    });

    es.onerror = () => {
      // SSE connection closed or failed
      setLoading(false);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jdId]);

  return (
    <div className="container page-content">
      <div className="shortlist-header animate-fade-in">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <span className="badge badge-primary">⚡ Stage A — Fast Ranking</span>
              <span className="badge badge-muted">PoC Mode</span>
            </div>
            <h1>Ranked Candidate Shortlist</h1>
          </div>

          <div>
            <Link href="/upload-jd" className="btn btn-ghost">
              ← New Role Match
            </Link>
          </div>
        </div>

        {data && (
          <div className="glass-card" style={{ marginTop: '1.5rem', padding: '1.25rem', background: 'rgba(59, 130, 246, 0.05)', borderColor: 'rgba(59, 130, 246, 0.2)' }}>
            <h4 style={{ fontSize: '0.8rem', color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
              Target Qualification Summary
            </h4>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
              {data.jd_summary}
            </p>
            <div className="shortlist-meta" style={{ marginTop: '0.75rem' }}>
              <span className="pill">👥 Total Pool: {data.total_pool_size} Candidates</span>
              <span className="pill" style={{ color: 'var(--success)' }}>🏆 Top {data.candidates?.length || 0} Shortlisted</span>
            </div>
          </div>
        )}
      </div>

      <StageIndicator stage={stage} totalCount={data?.candidates?.length || 0} stageBCount={stageBCount} />

      {/* Loading Skeletons */}
      {loading && (
        <div className="candidates-list">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="skeleton skeleton-card" />
          ))}
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">⚠️</div>
          <h3>Could not generate shortlist</h3>
          <p style={{ marginBottom: '1.5rem' }}>{error}</p>
          <button onClick={() => window.location.reload()} className="btn btn-primary">
            🔄 Retry Calculation
          </button>
        </div>
      )}

      {/* Empty Pool State */}
      {!loading && !error && data?.candidates?.length === 0 && (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">📭</div>
          <h3>No matching candidates retrieved</h3>
          <p style={{ marginBottom: '1.5rem' }}>
            We searched across {data.total_pool_size} parsed CVs in Qdrant, but none met the minimum semantic similarity threshold for this role description.
          </p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Tip: Make sure you have uploaded sample resume files into the background watcher directory (<code>./data/sample_resumes</code>) or via the API.
          </p>
        </div>
      )}

      {/* Candidate Cards List */}
      {!loading && !error && data?.candidates?.length > 0 && (
        <div className="candidates-list">
          {data.candidates.map((candidate, i) => (
            <CandidateCard
              key={candidate.candidate_id}
              candidate={candidate}
              jdId={jdId}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  );
}
