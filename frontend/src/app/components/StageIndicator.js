"use client";

import React from "react";

export default function StageIndicator({ stage, totalCount, stageBCount }) {
  const isStageB = stage === "B" || stageBCount > 0;
  const progressPercent = totalCount > 0 ? Math.min(100, Math.round((stageBCount / totalCount) * 100)) : 0;

  return (
    <div style={{
      padding: "1rem 1.5rem",
      background: "rgba(255, 255, 255, 0.04)",
      backdropFilter: "blur(12px)",
      borderRadius: "var(--radius-md)",
      border: "1px solid rgba(255, 255, 255, 0.1)",
      marginBottom: "2rem",
      display: "flex",
      flexDirection: "column",
      gap: "0.75rem"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span style={{
            display: "inline-block",
            padding: "0.35rem 0.75rem",
            background: isStageB ? "linear-gradient(135deg, var(--accent-blue), var(--accent-indigo))" : "rgba(245, 158, 11, 0.2)",
            color: isStageB ? "#fff" : "#f59e0b",
            borderRadius: "var(--radius-sm)",
            fontWeight: 600,
            fontSize: "0.85rem"
          }}>
            {isStageB ? "🧠 Stage B — LLM Re-Ranking Active" : "⚡ Stage A — Vector Retrieval Complete (<2s)"}
          </span>
          <span style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            {isStageB ? `Deep Gemini justification & risk audit (${stageBCount}/${totalCount})` : "Fast dense cosine + sparse BM25 fusion"}
          </span>
        </div>
      </div>

      {isStageB && totalCount > 0 && (
        <div style={{ width: "100%", background: "rgba(255, 255, 255, 0.08)", borderRadius: "999px", height: "6px", overflow: "hidden" }}>
          <div style={{
            width: `${progressPercent}%`,
            background: "linear-gradient(90deg, var(--accent-blue), var(--accent-indigo))",
            height: "100%",
            transition: "width 0.3s ease"
          }} />
        </div>
      )}
    </div>
  );
}
