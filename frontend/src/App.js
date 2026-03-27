import { useEffect, useMemo, useRef, useState } from "react";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
const WS_URL = process.env.REACT_APP_WS_URL || "ws://localhost:8000/ws";
const AGENT_ORDER = ["planner", "architect", "coder", "executor", "debugger", "evaluator"];

const styles = {
  page: {
    maxWidth: 1120,
    margin: "40px auto",
    fontFamily: "monospace",
    padding: "0 16px 40px",
    color: "#111827",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
    gap: 12,
    marginTop: 18,
  },
  card: {
    border: "1px solid #d1d5db",
    borderRadius: 10,
    padding: 14,
    background: "#ffffff",
  },
  timeline: {
    background: "#f8fafc",
    border: "1px solid #cbd5e1",
    borderRadius: 10,
    padding: 14,
    marginTop: 16,
  },
  section: {
    marginTop: 24,
  },
  panel: {
    background: "#f9fafb",
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: 12,
  },
};

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatEvent(event) {
  if (event.event === "task_started") return "Task started";
  if (event.event === "task_completed") return "Task completed";
  if (event.event === "agent_started") return `${titleCase(event.agent)} started`;
  if (event.event === "agent_completed") return `${titleCase(event.agent)} completed`;
  if (event.event === "handoff") return `${titleCase(event.from_agent)} -> ${titleCase(event.to_agent)}`;
  if (event.event === "tool_called") return `${titleCase(event.agent)} called ${event.tool}`;
  if (event.event === "tool_result") return `${titleCase(event.agent)} received ${event.tool} result`;
  if (event.event === "tool_mode_fallback") return `${titleCase(event.agent)} switched to plain generation after a large tool request`;
  return JSON.stringify(event);
}

function getStatusColor(status) {
  if (status === "completed") return "#166534";
  if (status === "running") return "#92400e";
  if (status === "idle") return "#475569";
  return "#9ca3af";
}

function buildAgentStatuses(events) {
  const statuses = Object.fromEntries(
    AGENT_ORDER.map((agent) => [agent, { state: "pending", detail: "Waiting" }]),
  );

  events.forEach((event) => {
    if (event.event === "agent_started" && statuses[event.agent]) {
      statuses[event.agent] = { state: "running", detail: "Working" };
    }
    if (event.event === "tool_called" && statuses[event.agent]) {
      statuses[event.agent] = { state: "running", detail: `Using ${event.tool}` };
    }
    if (event.event === "tool_result" && statuses[event.agent]) {
      statuses[event.agent] = { state: "running", detail: `Processed ${event.tool}` };
    }
    if (event.event === "tool_mode_fallback" && statuses[event.agent]) {
      statuses[event.agent] = { state: "running", detail: "Continuing without tools" };
    }
    if (event.event === "agent_completed" && statuses[event.agent]) {
      statuses[event.agent] = { state: "completed", detail: "Finished" };
    }
  });

  return statuses;
}

function App() {
  const [prd, setPrd] = useState("");
  const [events, setEvents] = useState([]);
  const [output, setOutput] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      setEvents((current) => [...current, event]);
    };
    ws.onerror = (e) => console.error("WebSocket error:", e);

    return () => ws.close();
  }, []);

  const filteredEvents = useMemo(() => {
    if (!activeTaskId) return events;
    return events.filter((event) => event.task_id === activeTaskId);
  }, [activeTaskId, events]);

  const agentStatuses = useMemo(() => buildAgentStatuses(filteredEvents), [filteredEvents]);
  const communicationEvents = useMemo(
    () => filteredEvents.filter((event) => ["task_started", "task_completed", "handoff", "tool_called", "tool_result", "tool_mode_fallback"].includes(event.event)),
    [filteredEvents],
  );
  const activeAgent = useMemo(() => {
    const running = AGENT_ORDER.find((agent) => agentStatuses[agent]?.state === "running");
    return running ? titleCase(running) : null;
  }, [agentStatuses]);

  const runTask = async () => {
    if (!prd.trim()) return;
    setLoading(true);
    setError(null);
    setOutput(null);
    setEvents([]);
    setActiveTaskId(null);
    try {
      const res = await fetch(`${API_URL}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prd }),
      });
      const data = await res.json();
      setActiveTaskId(data.task_id);
      setOutput(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadZip = async (taskId) => {
    try {
      const res = await fetch(`${API_URL}/download/${taskId}`);
      const contentType = res.headers.get("Content-Type") || "";
      if (!res.ok) {
        let message = "Download failed";
        try {
          const data = await res.json();
          message = data.detail || data.error || message;
        } catch (_) {
          // Ignore parse failures and use the fallback message.
        }
        throw new Error(message);
      }
      if (!contentType.includes("application/zip")) {
        throw new Error("Server did not return a zip archive");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers.get("Content-Disposition");
      const match = disposition && disposition.match(/filename="?([^"]+)"?/);
      a.download = match ? match[1] : `project_${taskId.slice(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Download failed: " + err.message);
    }
  };

  return (
    <div style={styles.page}>
      <h2>Devin v4 Dashboard</h2>

      <textarea
        rows={4}
        style={{ width: "100%", fontSize: 14, boxSizing: "border-box" }}
        placeholder="Describe what you want to build..."
        value={prd}
        onChange={(e) => setPrd(e.target.value)}
      />
      <br />
      <button onClick={runTask} disabled={loading || !prd.trim()} style={{ marginTop: 8 }}>
        {loading ? "Running..." : "Run Pipeline"}
      </button>

      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {(loading || filteredEvents.length > 0 || output) && (
        <div style={styles.section}>
          <h3>Agent Status</h3>
          <div style={styles.panel}>
            <div>Task: {loading ? "Running" : output ? "Completed" : "Idle"}</div>
            <div>Current Agent: {activeAgent || (output ? "Complete" : "Waiting")}</div>
            {activeTaskId && <div>Task ID: {activeTaskId}</div>}
          </div>
          <div style={styles.grid}>
            {AGENT_ORDER.map((agent) => (
              <div key={agent} style={styles.card}>
                <div style={{ fontSize: 12, color: "#6b7280" }}>{agent.toUpperCase()}</div>
                <div style={{ marginTop: 8, color: getStatusColor(agentStatuses[agent].state) }}>
                  {titleCase(agentStatuses[agent].state)}
                </div>
                <div style={{ marginTop: 6, fontSize: 12 }}>{agentStatuses[agent].detail}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {communicationEvents.length > 0 && (
        <div style={styles.section}>
          <h3>Agent Communication</h3>
          <div style={styles.timeline}>
            {communicationEvents.map((event, index) => (
              <div key={`${event.event}-${index}`} style={{ padding: "6px 0", borderBottom: index === communicationEvents.length - 1 ? "none" : "1px solid #e2e8f0" }}>
                {formatEvent(event)}
                {event.result_preview && (
                  <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>{event.result_preview}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {output && (
        <div style={{ marginTop: 24 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "#f0fff4",
              border: "1px solid #86efac",
              borderRadius: 6,
              padding: "10px 16px",
              marginBottom: 20,
            }}
          >
            <span style={{ fontSize: 14 }}>Pipeline complete - download your generated project as a zip</span>
            <button
              onClick={() => downloadZip(output.task_id)}
              style={{
                background: "#16a34a",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                padding: "8px 18px",
                cursor: "pointer",
                fontSize: 14,
                fontWeight: "bold",
              }}
            >
              Download ZIP
            </button>
          </div>

          <h3>Plan</h3>
          <pre style={{ background: "#f9f9f9", padding: 12, whiteSpace: "pre-wrap" }}>{output.plan}</pre>

          <h3>Architecture</h3>
          <pre style={{ background: "#f9f9f9", padding: 12, whiteSpace: "pre-wrap" }}>{output.architecture}</pre>

          <h3>Generated Code</h3>
          <pre style={{ background: "#1e1e1e", color: "#d4d4d4", padding: 16, overflowX: "auto" }}>{output.code}</pre>

          {output.execution_result && (
            <>
              <h3>Execution Output</h3>
              <pre style={{ background: "#efffef", padding: 12 }}>{output.execution_result}</pre>
            </>
          )}

          {output.evaluation && (
            <>
              <h3>Evaluation</h3>
              <pre style={{ background: "#f0f4ff", padding: 12, whiteSpace: "pre-wrap" }}>{output.evaluation}</pre>
            </>
          )}

          {output.errors?.length > 0 && (
            <>
              <h3>Errors ({output.retries} retries)</h3>
              <pre style={{ background: "#fff0f0", padding: 12 }}>{output.errors.join("\n---\n")}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
