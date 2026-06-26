'use client';

import { useState, useCallback } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * FeedbackButton — thumbs-up / thumbs-down with optimistic glow.
 *
 * Props:
 *   jdId         – job description id
 *   candidateId  – candidate id
 *   direction    – "up" | "down"
 */
export default function FeedbackButton({ jdId, candidateId, direction }) {
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);

  const signal = direction === 'up' ? 1 : -1;
  const icon = direction === 'up' ? '👍' : '👎';

  const handleClick = useCallback(async () => {
    if (loading) return;

    /* Optimistic toggle */
    const next = !active;
    setActive(next);

    if (!next) return; /* un-toggled — no need to POST */

    setLoading(true);
    try {
      const res = await fetch(`${API}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jd_id: jdId,
          candidate_id: candidateId,
          signal,
        }),
      });
      if (!res.ok) throw new Error('Feedback failed');
    } catch {
      /* Roll back on error */
      setActive(false);
    } finally {
      setLoading(false);
    }
  }, [active, loading, jdId, candidateId, signal]);

  const className = [
    'btn-icon',
    active && direction === 'up' && 'active',
    active && direction === 'down' && 'active-danger',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={className}
      onClick={handleClick}
      disabled={loading}
      title={direction === 'up' ? 'Good match' : 'Poor match'}
      aria-label={direction === 'up' ? 'Thumbs up' : 'Thumbs down'}
      aria-pressed={active}
    >
      {icon}
    </button>
  );
}
