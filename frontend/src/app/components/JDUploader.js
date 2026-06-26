'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function JDUploader() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const router = useRouter();

  const charCount = text.trim().length;
  const isValid = charCount >= 200;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isValid || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('http://localhost:8000/jd', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      // Redirect to shortlist view
      router.push(`/shortlist/${data.jd_id}`);
    } catch (err) {
      setError(err.message || 'Failed to submit Job Description');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="form-group">
      <label htmlFor="jd-text" className="form-label">
        Paste Job Description (Requirements, Responsibilities, Qualifications)
      </label>

      <textarea
        id="jd-text"
        className="form-textarea"
        placeholder="e.g. Senior Backend Engineer with 5+ years of experience in Python, FastAPI, and Distributed Systems. Must have experience with vector databases (Qdrant) and LLM orchestration..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={loading}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
        <span className={`char-count ${isValid ? 'valid' : ''}`}>
          {charCount} / 200 characters min {isValid ? '✓' : '(needs more context)'}
        </span>

        {error && (
          <span style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>
            ⚠️ {error}
          </span>
        )}
      </div>

      <div style={{ marginTop: '1.5rem', textAlign: 'right' }}>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!isValid || loading}
          style={{ width: '100%', padding: '1rem', fontSize: '1.05rem' }}
        >
          {loading ? (
            <>
              <div className="spinner" />
              Analyzing JD & Embedding Query...
            </>
          ) : (
            '⚡ Analyze & Find Matching Candidates'
          )}
        </button>
      </div>
    </form>
  );
}
