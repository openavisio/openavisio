"use client";

import { useState, useTransition } from "react";
import { saveAiModelsAction } from "./actions";

interface ModelInfo {
  name: string;
  size?: number;
  modified_at?: string;
  tasks: string[];
  hint?: string;
  tags: string[];
}

interface Props {
  models: ModelInfo[];
  initial: {
    extract_model?: string | null;
    classify_model?: string | null;
    chat_model?: string | null;
    vision_model?: string | null;
  };
}

const TASK_LABELS: Record<string, { label: string; description: string }> = {
  extract: { label: "Extraction", description: "Pulls diagnoses, medications, and appointments from documents" },
  classify: { label: "Classification", description: "Detects document type and provider" },
  chat: { label: "Chat", description: "Powers the AI Health Assistant" },
  vision: { label: "Vision OCR", description: "Reads image-only PDFs and scans" },
};

function ModelSelect({
  task,
  models,
  value,
  onChange,
}: {
  task: string;
  models: ModelInfo[];
  value: string;
  onChange: (v: string) => void;
}) {
  const { label, description } = TASK_LABELS[task];
  const recommended = models.filter((m) => m.tasks.includes(task));
  const others = models.filter((m) => !m.tasks.includes(task));

  return (
    <div className="py-3 border-b last:border-0">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-medium">{label}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{description}</div>
        </div>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="text-xs font-mono border rounded px-2 py-1.5 bg-background min-w-[200px] max-w-[280px]"
        >
          <option value="">— not set —</option>
          {recommended.length > 0 && (
            <optgroup label="Recommended">
              {recommended.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))}
            </optgroup>
          )}
          {others.length > 0 && (
            <optgroup label="Other available models">
              {others.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>
      {value && (() => {
        const selected = models.find((m) => m.name === value);
        return selected?.hint ? (
          <div className="mt-1.5 text-xs text-muted-foreground pl-0">
            {selected.tags.includes("medical") && (
              <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 text-[10px] font-medium">medical</span>
            )}
            {selected.tags.includes("vision") && (
              <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 text-[10px] font-medium">vision</span>
            )}
            {selected.tags.includes("cloud") && (
              <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300 text-[10px] font-medium">cloud</span>
            )}
            {selected.hint}
          </div>
        ) : null;
      })()}
    </div>
  );
}

export function AiModelConfig({ models, initial }: Props) {
  const [config, setConfig] = useState({
    extract_model: initial.extract_model ?? "",
    classify_model: initial.classify_model ?? "",
    chat_model: initial.chat_model ?? "",
    vision_model: initial.vision_model ?? "",
  });
  const [pending, startTransition] = useTransition();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = () => {
    setError(null);
    startTransition(async () => {
      const result = await saveAiModelsAction({
        extract_model: config.extract_model || null,
        classify_model: config.classify_model || null,
        chat_model: config.chat_model || null,
        vision_model: config.vision_model || null,
      });
      if (result.error) {
        setError(result.error);
      } else {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    });
  };

  const setField = (field: keyof typeof config) => (v: string) =>
    setConfig((c) => ({ ...c, [field]: v }));

  return (
    <div className="mt-6 rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">Model Configuration</div>
      <div className="px-4">
        {(["extract", "classify", "chat", "vision"] as const).map((task) => (
          <ModelSelect
            key={task}
            task={task}
            models={models}
            value={config[`${task}_model`]}
            onChange={setField(`${task}_model`)}
          />
        ))}
      </div>
      <div className="px-4 py-3 border-t flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={pending}
          className="px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
        >
          {pending ? "Saving…" : "Save"}
        </button>
        {saved && <span className="text-sm text-green-600">Saved</span>}
        {error && <span className="text-sm text-red-500">{error}</span>}
      </div>
    </div>
  );
}
