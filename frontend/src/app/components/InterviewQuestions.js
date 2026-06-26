"use client";

import React, { useState } from "react";

export default function InterviewQuestions({ jdId, candidateId, riskFlags }) {
  const [questions, setQuestions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);

  async function handleToggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (questions) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/jd/${jdId}/candidate/${candidateId}/interview-questions`);
      if (!res.ok) throw new Error("Failed to load interview questions");
      const data = await res.json();
      setQuestions(data.questions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: "1rem", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "1rem" }}>
      <button
        onClick={handleToggle}
        style={{
          background: "rgba(255, 255, 255, 0.05)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          color: "var(--accent-blue)",
          padding: "0.5rem 1rem",
          borderRadius: "var(--radius-sm)",
          cursor: "pointer",
          fontSize: "0.85rem",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: "0.5rem"
        }}
      >
        <span>🎯 {open ? "Hide Interview Guide" : "Generate Custom Interview Guide"}</span>
        {riskFlags && riskFlags.length > 0 && (
          <span style={{ fontSize: "0.75rem", background: "rgba(239, 68, 68, 0.2)", color: "#ef4444", padding: "0.15rem 0.5rem", borderRadius: "999px" }}>
            Probes {riskFlags.length} Risks
          </span>
        )}
      </button>

      {open && (
        <div style={{ marginTop: "1rem", padding: "1rem", background: "rgba(0, 0, 0, 0.2)", borderRadius: "var(--radius-md)" }}>
          {loading && <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>🧠 Generating targeted questions probing weakest evidence...</p>}
          {error && <p style={{ color: "#ef4444", fontSize: "0.9rem" }}>⚠️ {error}</p>}
          
          {questions && questions.length === 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No specific risk questions generated.</p>
          )}

          {questions && questions.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <h5 style={{ fontSize: "0.9rem", color: "#fff", marginBottom: "0.25rem" }}>Recommended Interview Script:</h5>
              {questions.map((q, idx) => (
                <div key={idx} style={{ padding: "0.75rem", background: "rgba(255, 255, 255, 0.03)", borderLeft: "3px solid var(--accent-indigo)", borderRadius: "4px" }}>
                  <p style={{ color: "#e2e8f0", fontSize: "0.9rem", marginBottom: "0.25rem", fontWeight: 500 }}>{q.question}</p>
                  <span style={{ fontSize: "0.75rem", color: "var(--accent-blue)" }}>Target: {q.target_risk}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
