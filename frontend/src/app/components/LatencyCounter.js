"use client";

import React, { useState, useEffect } from "react";

export default function LatencyCounter() {
  const [ms, setMs] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const interval = setInterval(() => {
      setMs(Math.round(performance.now() - start));
    }, 50);

    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      position: "fixed",
      bottom: "1rem",
      right: "1rem",
      background: "rgba(0, 0, 0, 0.6)",
      backdropFilter: "blur(8px)",
      border: "1px solid rgba(255, 255, 255, 0.15)",
      padding: "0.4rem 0.8rem",
      borderRadius: "999px",
      fontSize: "0.75rem",
      color: "#a78bfa",
      zIndex: 50,
      display: "flex",
      alignItems: "center",
      gap: "0.4rem"
    }}>
      <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }} />
      <span>Session Uptime: {ms} ms</span>
    </div>
  );
}
