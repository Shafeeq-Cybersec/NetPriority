/**
 * FlowForm — flow metadata input form.
 *
 * UX improvements:
 *   - "Custom" mode replaces the old "Clear" button (#6).
 *     Clicking "Custom" resets all fields to empty values and shows a
 *     dashed-border indicator so the user knows they are in free-entry mode.
 *   - Preset buttons fill the form with a concrete example for each category.
 *   - A "Reset" button inside Custom mode clears back to empty again.
 *   - Preset buttons exit Custom mode.
 */

import { useState } from "react";
import type { FlowSubmit, Protocol } from "../api";

interface FlowFormProps {
  onSubmit: (flow: FlowSubmit) => void;
  loading: boolean;
}

interface FormState {
  src_ip: string;
  dst_ip: string;
  src_port: string;
  dst_port: string;
  protocol: Protocol;
  packet_count: string;
  byte_count: string;
  duration_seconds: string;
  inter_arrival_ms: string;
}

const CUSTOM_EMPTY: FormState = {
  src_ip: "",
  dst_ip: "",
  src_port: "",
  dst_port: "",
  protocol: "UDP",
  packet_count: "",
  byte_count: "",
  duration_seconds: "",
  inter_arrival_ms: "",
};

const PRESETS: { label: string; color: string; flow: FormState }[] = [
  {
    label: "Gaming",
    color: "from-violet-500 to-purple-500",
    flow: {
      src_ip: "192.168.1.50",
      dst_ip: "203.0.113.10",
      src_port: "52000",
      dst_port: "27015",
      protocol: "UDP",
      packet_count: "800",
      byte_count: "160000",
      duration_seconds: "30",
      inter_arrival_ms: "15",
    },
  },
  {
    label: "Video",
    color: "from-blue-500 to-cyan-500",
    flow: {
      src_ip: "198.51.100.1",
      dst_ip: "192.168.1.100",
      src_port: "5004",
      dst_port: "5004",
      protocol: "UDP",
      packet_count: "2000",
      byte_count: "20000000",
      duration_seconds: "20",
      inter_arrival_ms: "10",
    },
  },
  {
    label: "Signaling",
    color: "from-amber-500 to-orange-500",
    flow: {
      src_ip: "10.0.0.5",
      dst_ip: "10.0.0.1",
      src_port: "60000",
      dst_port: "5060",
      protocol: "UDP",
      packet_count: "20",
      byte_count: "2000",
      duration_seconds: "5",
      inter_arrival_ms: "250",
    },
  },
  {
    label: "Bulk",
    color: "from-rose-500 to-pink-500",
    flow: {
      src_ip: "192.168.1.20",
      dst_ip: "185.60.219.35",
      src_port: "54321",
      dst_port: "445",
      protocol: "TCP",
      packet_count: "5000",
      byte_count: "70000000",
      duration_seconds: "30",
      inter_arrival_ms: "",
    },
  },
];

function num(v: string): number | undefined {
  const n = parseFloat(v);
  return isNaN(n) ? undefined : n;
}

export default function FlowForm({ onSubmit, loading }: FlowFormProps) {
  const [form, setForm] = useState<FormState>(PRESETS[0].flow); // default: Gaming preset
  const [isCustom, setIsCustom] = useState(false);             // #6 — custom mode flag
  const [activePreset, setActivePreset] = useState<string>("Gaming");
  const [error, setError] = useState("");

  const set = (key: keyof FormState, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  // Enter custom mode: clear all fields, show dashed indicator
  const enterCustomMode = () => {
    setIsCustom(true);
    setActivePreset("");
    setForm(CUSTOM_EMPTY);
    setError("");
  };

  // Load a preset: exit custom mode, fill form
  const loadPreset = (p: (typeof PRESETS)[number]) => {
    setIsCustom(false);
    setActivePreset(p.label);
    setForm(p.flow);
    setError("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.src_ip.trim() || !form.dst_ip.trim()) {
      setError("Source IP and Destination IP are required.");
      return;
    }
    const payload: FlowSubmit = {
      src_ip: form.src_ip.trim(),
      dst_ip: form.dst_ip.trim(),
      src_port: num(form.src_port),
      dst_port: num(form.dst_port),
      protocol: form.protocol,
      packet_count: num(form.packet_count),
      byte_count: num(form.byte_count),
      duration_seconds: num(form.duration_seconds),
      inter_arrival_ms: num(form.inter_arrival_ms),
    };
    onSubmit(payload);
  };

  // Card border changes in custom mode
  const cardBorder = isCustom
    ? "border-dashed border-indigo-500/40"
    : "border-white/10";

  return (
    <div
      className={`rounded-2xl border ${cardBorder} bg-white/5 p-6 backdrop-blur-xl transition-all duration-200`}
    >
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">
          Submit a Flow for Classification
        </h2>
        {/* Custom mode badge */}
        {isCustom && (
          <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-xs font-medium text-indigo-300">
            custom entry
          </span>
        )}
      </div>
      <p className="mb-4 text-xs text-slate-500">
        Enter flow metadata — ports, protocol, packet size and timing. No
        payload is inspected.
      </p>

      {/* Preset / Custom buttons */}
      <div className="mb-5 flex flex-wrap gap-2">
        <span className="self-center text-xs text-slate-500">Quick fill:</span>

        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => loadPreset(p)}
            className={`rounded-lg bg-gradient-to-r ${p.color} px-3 py-1 text-xs font-semibold text-white shadow transition ${
              activePreset === p.label
                ? "ring-2 ring-white/30 ring-offset-1 ring-offset-slate-950"
                : "hover:opacity-90"
            }`}
          >
            {p.label}
          </button>
        ))}

        {/* Custom mode button (#6) */}
        <button
          type="button"
          onClick={enterCustomMode}
          className={`rounded-lg border px-3 py-1 text-xs font-semibold transition ${
            isCustom
              ? "border-indigo-500/50 bg-indigo-500/10 text-indigo-300"
              : "border-white/10 text-slate-400 hover:border-white/30 hover:text-slate-200"
          }`}
        >
          Custom
        </button>

        {/* Reset inside custom mode */}
        {isCustom && (
          <button
            type="button"
            onClick={() => { setForm(CUSTOM_EMPTY); setError(""); }}
            className="rounded-lg border border-white/10 px-3 py-1 text-xs text-slate-500 transition hover:border-white/20 hover:text-slate-400"
          >
            Reset fields
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* IPs */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Source IP *" value={form.src_ip} onChange={(v) => set("src_ip", v)} placeholder="192.168.1.10" />
          <Field label="Destination IP *" value={form.dst_ip} onChange={(v) => set("dst_ip", v)} placeholder="203.0.113.1" />
        </div>

        {/* Ports + protocol */}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Source Port" value={form.src_port} onChange={(v) => set("src_port", v)} placeholder="52000" type="number" />
          <Field label="Dest Port" value={form.dst_port} onChange={(v) => set("dst_port", v)} placeholder="27015" type="number" />
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-400">Protocol</label>
            <select
              value={form.protocol}
              onChange={(e) => set("protocol", e.target.value as Protocol)}
              className="rounded-lg border border-white/10 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
            >
              <option value="TCP">TCP</option>
              <option value="UDP">UDP</option>
              <option value="Other">Other</option>
            </select>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Packet Count" value={form.packet_count} onChange={(v) => set("packet_count", v)} placeholder="800" type="number" />
          <Field label="Byte Count" value={form.byte_count} onChange={(v) => set("byte_count", v)} placeholder="160000" type="number" />
          <Field label="Duration (s)" value={form.duration_seconds} onChange={(v) => set("duration_seconds", v)} placeholder="30" type="number" />
          <Field label="Inter-arrival (ms)" value={form.inter_arrival_ms} onChange={(v) => set("inter_arrival_ms", v)} placeholder="15" type="number" />
        </div>

        {error && (
          <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-gradient-to-r from-indigo-500 to-cyan-500 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Classifying…" : "Classify Flow →"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-400">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={type === "number" ? "0" : undefined}
        className="rounded-lg border border-white/10 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
      />
    </div>
  );
}
