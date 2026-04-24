"use client";

import { useState, useEffect } from "react";
import { config } from "@/lib/config";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addProviderKey, removeProviderKey, getProviders } from "@/lib/api/providers";

const XAI_MODELS = [
  "grok-4-1-fast-reasoning",
  "grok-4-fast-reasoning",
  "grok-3-mini-fast",
] as const;

const DEFAULT_MODEL = "grok-4-1-fast-reasoning";

type TestStatus = "idle" | "testing" | "ok" | "error";
type KeyStatus = "idle" | "saving" | "saved" | "error";

export function ProviderSection() {
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [apiKey, setApiKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [keyStatus, setKeyStatus] = useState<KeyStatus>("idle");
  const [keyError, setKeyError] = useState("");
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testError, setTestError] = useState("");

  useEffect(() => {
    const saved = config.getModel();
    setModel(saved && (XAI_MODELS as readonly string[]).includes(saved) ? saved : DEFAULT_MODEL);
    config.setProvider("xai");
    getProviders()
      .then((data) => {
        const xai = data.providers.find((p) => p.id === "xai");
        if (xai) setKeyConfigured(xai.configured);
      })
      .catch(() => {});
  }, []);

  function handleModelChange(v: string) {
    setModel(v);
    config.setModel(v);
  }

  async function handleSaveKey() {
    if (!apiKey.trim()) return;
    setKeyStatus("saving");
    setKeyError("");
    try {
      await addProviderKey("xai", apiKey.trim());
      setKeyConfigured(true);
      setApiKey("");
      setKeyStatus("saved");
    } catch {
      setKeyStatus("error");
      setKeyError("Failed to save key");
    }
  }

  async function handleRemoveKey() {
    setKeyStatus("saving");
    setKeyError("");
    try {
      await removeProviderKey("xai");
      setKeyConfigured(false);
      setKeyStatus("idle");
    } catch {
      setKeyStatus("error");
      setKeyError("Failed to remove key");
    }
  }

  async function handleTestConnection() {
    setTestStatus("testing");
    setTestError("");
    try {
      const res = await fetch("/health");
      const data = await res.json();
      if (res.ok && data.status === "healthy") {
        setTestStatus("ok");
      } else {
        setTestStatus("error");
        setTestError(data.status ?? "Server returned non-healthy status");
      }
    } catch (err) {
      setTestStatus("error");
      setTestError(String(err));
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">xAI / Grok</CardTitle>
          <CardDescription>
            API key and model used when triggering init or sync from the UI.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label>API Key</Label>
              {keyConfigured && (
                <Badge variant="outline" className="text-xs text-green-600 dark:text-green-400 border-green-500/40">
                  ✓ configured
                </Badge>
              )}
            </div>
            <div className="flex gap-2">
              <Input
                type="password"
                placeholder={keyConfigured ? "••••••••••••••••" : "xai-…"}
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setKeyStatus("idle"); }}
                onKeyDown={(e) => { if (e.key === "Enter") handleSaveKey(); }}
                className="font-mono flex-1"
              />
              <button
                onClick={handleSaveKey}
                disabled={!apiKey.trim() || keyStatus === "saving"}
                className="text-sm px-3 py-1.5 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-bg-secondary)] disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {keyStatus === "saving" ? "Saving…" : "Save"}
              </button>
              {keyConfigured && (
                <button
                  onClick={handleRemoveKey}
                  disabled={keyStatus === "saving"}
                  className="text-sm px-3 py-1.5 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-bg-secondary)] disabled:opacity-50 transition-colors text-[var(--color-outdated)]"
                >
                  Remove
                </button>
              )}
            </div>
            {keyStatus === "saved" && (
              <p className="text-xs text-green-600 dark:text-green-400">✓ Key saved</p>
            )}
            {keyStatus === "error" && (
              <p className="text-xs text-[var(--color-outdated)]">{keyError}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Model</Label>
            <Select value={model} onValueChange={handleModelChange}>
              <SelectTrigger className="w-72 font-mono">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {XAI_MODELS.map((m) => (
                  <SelectItem key={m} value={m} className="font-mono">
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Server Connection</CardTitle>
          <CardDescription>
            Test that the repowise server is reachable and healthy.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTestConnection}
              disabled={testStatus === "testing"}
              className="text-sm px-3 py-1.5 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-bg-secondary)] disabled:opacity-50 transition-colors"
            >
              {testStatus === "testing" ? "Testing…" : "Test connection"}
            </button>
            {testStatus === "ok" && (
              <span className="text-sm text-green-600 dark:text-green-400">✓ Server healthy</span>
            )}
            {testStatus === "error" && (
              <span className="text-sm text-red-600 dark:text-red-400">
                ✗ {testError || "Connection failed"}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
