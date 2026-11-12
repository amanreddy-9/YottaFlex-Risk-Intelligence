import React, { useEffect, useState } from "react";
import { Bookmark, Plus, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { SavedViewItem } from "../types/workbench";

interface SavedPresetsBarProps {
  workspace: "queue" | "alerts";
  currentFilters: Record<string, string | boolean>;
  onApplyPreset: (filters: Record<string, string | boolean>) => void;
}

export const SavedPresetsBar: React.FC<SavedPresetsBarProps> = ({
  workspace,
  currentFilters,
  onApplyPreset,
}) => {
  const [presets, setPresets] = useState<SavedViewItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");

  const load = () => {
    api.savedViews(workspace).then((res) => setPresets(res.items)).catch(() => {});
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createSavedView({ workspace, name: name.trim(), filters: currentFilters });
      setName("");
      setAdding(false);
      load();
    } catch {
      // ignore validation failure cleanly
    }
  };

  const handleDelete = async (viewId: string) => {
    try {
      await api.deleteSavedView(viewId);
      load();
    } catch {
      // ignore
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px]">
      <span className="inline-flex items-center gap-1 font-semibold text-slate-600 dark:text-zinc-400">
        <Bookmark className="w-3 h-3 text-azure-600 dark:text-sky-400" />
        Saved Views:
      </span>
      {presets.map((p) => (
        <span
          key={p.view_id}
          className="glass-pill inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-slate-800 dark:text-zinc-200"
        >
          <button
            type="button"
            onClick={() => onApplyPreset(p.filters)}
            className="font-semibold hover:text-azure-700 dark:hover:text-sky-300 transition"
          >
            {p.name}
          </button>
          <button
            type="button"
            onClick={() => handleDelete(p.view_id)}
            title="Remove preset"
            className="text-slate-400 hover:text-rose-500 transition"
          >
            <Trash2 className="w-2.5 h-2.5" />
          </button>
        </span>
      ))}
      {!adding ? (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-azure-500/12 text-azure-700 dark:bg-sky-500/20 dark:text-sky-300 font-semibold hover:bg-azure-500/20 transition"
        >
          <Plus className="w-3 h-3" /> Save Current Filter
        </button>
      ) : (
        <form onSubmit={handleSave} className="inline-flex items-center gap-1.5">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Preset name..."
            className="glass-pill px-2.5 py-0.5 rounded-full text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 w-36 focus:outline-none"
          />
          <button type="submit" className="px-2 py-0.5 rounded-full bg-azure-600 text-white font-semibold">
            Save
          </button>
          <button type="button" onClick={() => setAdding(false)} className="text-slate-500 underline">
            Cancel
          </button>
        </form>
      )}
    </div>
  );
};
