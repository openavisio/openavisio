"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

interface LogEntry {
  ts: string;
  level: string;
  logger: string;
  msg: string;
  source: string;
  exc?: string;
}

interface PipelineTask {
  id: string;
  file_name: string | null;
  patient_name: string;
  processing_status: string;
  pipeline_stage: string | null;
  processing_error: string | null;
  updated_at: string;
}

interface TaskRun {
  id: string;
  task_id: string;
  task_name: string;
  args_summary: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
}

const TASKRUN_VARIANT: Record<string, string> = {
  running: "info",
  success: "success",
  failure: "destructive",
};

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

const LEVEL_BADGE: Record<string, string> = {
  DEBUG: "text-muted-foreground bg-muted border-transparent",
  INFO: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 border-transparent",
  WARNING: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300 border-transparent",
  ERROR: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 border-transparent",
  CRITICAL: "bg-red-200 text-red-900 dark:bg-red-900/50 dark:text-red-200 border-transparent",
};

const STATUS_VARIANT: Record<string, string> = {
  pending: "muted",
  processing: "info",
  completed: "success",
  failed: "destructive",
};

function LevelChip({ level, active, onClick }: { level: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-opacity ${LEVEL_BADGE[level] ?? ""} ${active ? "opacity-100" : "opacity-30"}`}
    >
      {level}
    </button>
  );
}

export function LogsClient() {
  const [tab, setTab] = useState<"logs" | "tasks" | "jobs">("logs");

  // -- Log stream state --
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeLevel, setActiveLevel] = useState<Set<string>>(new Set(LEVELS));
  const [autoScroll, setAutoScroll] = useState(true);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // -- Tasks state --
  const [tasks, setTasks] = useState<PipelineTask[]>([]);
  const [taskRuns, setTaskRuns] = useState<TaskRun[]>([]);


  const toggleLevel = useCallback((level: string) => {
    setActiveLevel((prev) => {
      const next = new Set(prev);
      next.has(level) ? next.delete(level) : next.add(level);
      return next;
    });
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 16);
  };

  // Load DB history on mount
  useEffect(() => {
    fetch(`/api/admin/logs/history?limit=500`)
      .then((r) => (r.ok ? r.json() : []))
      .then((entries: LogEntry[]) => setLogs(entries))
      .catch(() => {});
  }, []);

  // SSE connection (same-origin proxy — token stays server-side, issue #51)
  useEffect(() => {
    const es = new EventSource(`/api/admin/logs/stream`);

    es.onopen = () => setConnected(true);
    es.onmessage = (event) => {
      try {
        const entry: LogEntry = JSON.parse(event.data);
        setLogs((prev) => (prev.length >= 1000 ? [...prev.slice(-999), entry] : [...prev, entry]));
      } catch {}
    };
    es.onerror = () => setConnected(false);

    return () => {
      es.close();
      setConnected(false);
    };
  }, []);

  // Tasks polling
  useEffect(() => {
    if (tab !== "tasks") return;

    const fetchTasks = async () => {
      try {
        const res = await fetch(`/api/admin/logs/tasks`);
        if (res.ok) setTasks(await res.json());
      } catch {}
    };

    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, [tab]);

  // Task-runs polling (all Celery job types)
  useEffect(() => {
    if (tab !== "jobs") return;

    const fetchRuns = async () => {
      try {
        const res = await fetch(`/api/admin/logs/task-runs?limit=200`);
        if (res.ok) setTaskRuns(await res.json());
      } catch {}
    };

    fetchRuns();
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, [tab]);

  const filteredLogs = logs.filter((l) => activeLevel.has(l.level));

  return (
    <div className="flex flex-col gap-4">
      {/* Tab bar */}
      <div className="flex border-b">
        {(["logs", "tasks", "jobs"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "logs" ? "Application Logs" : t === "tasks" ? "Processing Pipeline" : "All Jobs"}
          </button>
        ))}
      </div>

      {tab === "logs" && (
        <div className="flex flex-col gap-3">
          {/* Toolbar */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground mr-1">Level:</span>
            {LEVELS.map((l) => (
              <LevelChip key={l} level={l} active={activeLevel.has(l)} onClick={() => toggleLevel(l)} />
            ))}
            <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={`size-1.5 rounded-full ${connected ? "bg-green-500" : "bg-muted-foreground"}`} />
              {connected ? "Live" : "Connecting…"}
            </div>
          </div>

          {/* Terminal */}
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="h-[600px] overflow-y-auto rounded-lg border bg-zinc-950 dark:bg-zinc-950 font-mono text-xs"
          >
            {filteredLogs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-zinc-500">
                {connected ? "Waiting for log entries…" : "Connecting to log stream…"}
              </div>
            ) : (
              <table className="w-full border-collapse">
                <tbody>
                  {filteredLogs.map((entry, i) => (
                    <tr key={i} className="hover:bg-white/5 align-top">
                      <td className="px-3 py-0.5 whitespace-nowrap text-zinc-500 select-none w-[160px]">
                        {entry.ts.replace("T", " ").slice(0, 23)}
                      </td>
                      <td className="px-2 py-0.5 whitespace-nowrap w-[80px]">
                        <span className={`px-1.5 py-px rounded text-[10px] font-bold ${LEVEL_BADGE[entry.level] ?? ""}`}>
                          {entry.level}
                        </span>
                      </td>
                      <td className="px-2 py-0.5 whitespace-nowrap text-zinc-400 max-w-[180px] truncate w-[180px]">
                        {entry.logger}
                      </td>
                      <td className="px-2 py-0.5 text-zinc-200 break-all">
                        {entry.msg}
                        {entry.exc && (
                          <pre className="mt-0.5 text-red-400 whitespace-pre-wrap">{entry.exc}</pre>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {!autoScroll && (
            <button
              onClick={() => {
                setAutoScroll(true);
                if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
              }}
              className="self-end text-xs text-muted-foreground underline"
            >
              Scroll to bottom
            </button>
          )}
        </div>
      )}

      {tab === "tasks" && (
        <div className="rounded-xl border bg-card overflow-hidden">
          {tasks.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">No pipeline tasks found.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Document</th>
                  <th className="px-4 py-3 text-left font-medium">Patient</th>
                  <th className="px-4 py-3 text-left font-medium">Stage</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Updated</th>
                  <th className="px-4 py-3 text-left font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono truncate max-w-[180px]">
                      {task.file_name ?? task.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 text-xs">{task.patient_name}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{task.pipeline_stage ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={(STATUS_VARIANT[task.processing_status] ?? "outline") as any}>
                        {task.processing_status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(task.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-destructive truncate max-w-[200px]" title={task.processing_error ?? ""}>
                      {task.processing_error ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "jobs" && (
        <div className="rounded-xl border bg-card overflow-hidden">
          {taskRuns.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">No task runs recorded yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Task</th>
                  <th className="px-4 py-3 text-left font-medium">Args</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Started</th>
                  <th className="px-4 py-3 text-left font-medium">Finished</th>
                  <th className="px-4 py-3 text-left font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {taskRuns.map((run) => (
                  <tr key={run.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono truncate max-w-[220px]" title={run.task_name}>
                      {run.task_name.split(".").pop()}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground truncate max-w-[180px]" title={run.args_summary ?? ""}>
                      {run.args_summary ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={(TASKRUN_VARIANT[run.status] ?? "outline") as any}>{run.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {run.started_at ? formatDate(run.started_at) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {run.finished_at ? formatDate(run.finished_at) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-destructive truncate max-w-[200px]" title={run.error ?? ""}>
                      {run.error ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
