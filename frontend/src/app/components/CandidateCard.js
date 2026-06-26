'use client';

import { useState } from 'react';
import FeedbackButton from './FeedbackButton';
import InterviewQuestions from './InterviewQuestions';

export default function CandidateCard({ candidate, jdId, index = 0 }) {
  const [expanded, setExpanded] = useState(false);

  const {
    candidate_id,
    rank,
    stage_a_score,
    dense_score,
    confidence,
    metadata = {},
    name = "Candidate",
    fit_score,
    justification,
    risk_flags,
  } = candidate;

  // Convert score (0.0 to 1.0+) to percentage
  const scorePercent = Math.min(100, Math.round(stage_a_score * 100));
  const densePercent = Math.min(100, Math.round(dense_score * 100));
  const displayPercent = fit_score !== undefined ? Math.round(fit_score) : scorePercent;

  // Determine confidence badge style
  const confStyle =
    confidence === 'high'
      ? 'badge-success'
      : confidence === 'low'
      ? 'badge-danger'
      : 'badge-primary';

  return (
    <div
      className="glass-card animate-slide-up"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="candidate-card">
        <div className="rank-badge">#{rank}</div>

        <div className="candidate-card-body">
          <div className="candidate-card-header">
            <div>
              <span className="candidate-name">{name}</span>
              <span style={{ marginLeft: '0.75rem' }} className={`badge ${confStyle}`}>
                {confidence} confidence
              </span>
              {fit_score !== undefined && (
                <span style={{ marginLeft: '0.5rem', background: 'linear-gradient(135deg, var(--primary), var(--accent))', color: '#fff' }} className="badge">
                  🧠 Stage B Verified
                </span>
              )}
            </div>

            <div className="candidate-actions">
              <FeedbackButton jdId={jdId} candidateId={candidate_id} />
            </div>
          </div>

          {/* Main Fit Score Bar */}
          <div className="candidate-score">
            <span className="candidate-score-label">{fit_score !== undefined ? "Gemini Stage B Match" : "Stage A Score"}</span>
            <div className="score-bar-container">
              <div
                className="score-bar-fill"
                style={{ width: `${displayPercent}%`, background: fit_score !== undefined ? 'linear-gradient(90deg, #3b82f6, #8b5cf6)' : undefined }}
              />
            </div>
            <span className="candidate-score-value">{displayPercent}%</span>
          </div>

          {/* Stage B Justification & Risks */}
          {justification && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <h5 style={{ fontSize: '0.85rem', color: '#60a5fa', marginBottom: '0.35rem' }}>⚖️ Judge Synthesis:</h5>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{justification}</p>
              
              {risk_flags && risk_flags.length > 0 && (
                <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#ef4444', fontWeight: 600 }}>Risks:</span>
                  {risk_flags.map((rf, idx) => (
                    <span key={idx} style={{ fontSize: '0.75rem', background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', padding: '0.1rem 0.5rem', borderRadius: '4px' }}>
                      {rf}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Metadata Pills */}
          <div className="pills" style={{ marginTop: '1rem' }}>
            {metadata.domain_years !== undefined && metadata.domain_years !== null && (
              <span className="pill">💼 {metadata.domain_years} yrs exp</span>
            )}
            {metadata.education_level && (
              <span className="pill">🎓 {metadata.education_level.toUpperCase()}</span>
            )}
            {metadata.location && (
              <span className="pill">📍 {metadata.location}</span>
            )}
            {metadata.certifications && metadata.certifications.length > 0 && (
              <span className="pill">📜 {metadata.certifications.length} Certs</span>
            )}
          </div>

          {/* Interview Questions Guide */}
          <InterviewQuestions jdId={jdId} candidateId={candidate_id} riskFlags={risk_flags} />

          {/* Expandable Details */}
          <div className="candidate-details">
            <button
              type="button"
              className="candidate-details-toggle"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? '▲ Hide Profile Highlights' : '▼ View Profile Highlights'}
            </button>

            {expanded && (
              <div className="animate-fade-in" style={{ marginTop: '1rem' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Extracted Certifications & Skills
                </h4>
                {metadata.certifications && metadata.certifications.length > 0 ? (
                  <div className="pills" style={{ marginBottom: '1rem' }}>
                    {metadata.certifications.map((c, i) => (
                      <span key={i} className="pill" style={{ borderColor: 'var(--border-glow)', color: 'var(--primary)' }}>
                        ★ {c}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>No specific certifications detected.</p>
                )}

                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Raw File Reference
                </h4>
                <div className="candidate-chunk">
                  <code style={{ fontSize: '0.8rem' }}>ID: {candidate_id}</code>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
