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
import { addProviderKey, removeProviderKey, getProviders, setActiveProvider } from "@/lib/api/providers";
import type { ProviderInfo } from "@/lib/api/types";

const DEFAULT_PROVIDER = "xai";
const DEFAULT_MODEL = "grok-4-1-fast-reasoning";

type TestStatus = "idle" | "testing" | "ok" | "error";
type KeyStatus = "idle" | "saving" | "saved" | "error";

export function ProviderSection() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [providerId, setProviderId] = useState(DEFAULT_PROVIDER);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [apiKey, setApiKey] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [keyStatus, setKeyStatus] = useState<KeyStatus>("idle");
  const [keyError, setKeyError] = useState("");
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testError, setTestError] = useState("");

  useEffect(() => {
    getProviders()
      .then((data) => {
        setProviders(data.providers);
        const activeId = data.active.provider ?? config.getProvider() ?? DEFAULT_PROVIDER;
        const activeProvider =
          data.providers.find((p) => p.id === activeId) ??
          data.providers.find((p) => p.id === DEFAULT_PROVIDER) ??
          data.providers[0];
        const nextProviderId = activeProvider?.id ?? DEFAULT_PROVIDER;
        const savedModel = config.getModel();
        const nextModel =
          data.active.model ??
          (savedModel && activeProvider?.models.includes(savedModel) ? savedModel : undefined) ??
          activeProvider?.default_model ??
          DEFAULT_MODEL;
        setProviderId(nextProviderId);
        setModel(nextModel);
        setKeyConfigured(Boolean(activeProvider?.configured));
        config.setProvider(nextProviderId);
        config.setModel(nextModel);
      })
      .catch(() => {});
  }, []);

  function handleModelChange(v: string) {
    setModel(v);
    config.setModel(v);
    setActiveProvider(providerId, v).catch(() => {});
  }

  function handleProviderChange(v: string) {
    const selected = providers.find((p) => p.id === v);
    const nextModel = selected?.default_model ?? DEFAULT_MODEL;
    setProviderId(v);
    setModel(nextModel);
    setKeyConfigured(Boolean(selected?.configured));
    config.setProvider(v);
    config.setModel(nextModel);
    setActiveProvider(v, nextModel).catch(() => {});
  }

  async function handleSaveKey() {
    if (!apiKey.trim()) return;
    setKeyStatus("saving");
    setKeyError("");
    try {
      await addProviderKey(providerId, apiKey.trim());
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
      await removeProviderKey(providerId);
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

  const selectedProvider = providers.find((p) => p.id === providerId);
  const selectedModels = selectedProvider?.models ?? [];
  const requiresKey = true;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Model Provider</CardTitle>
          <CardDescription>
            xAI / Grok is the only supported LLM provider.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Provider</Label>
            <Select value={providerId} onValueChange={handleProviderChange}>
              <SelectTrigger className="w-72">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(providers.length ? providers : [{ id: DEFAULT_PROVIDER, name: "xAI / Grok" } as ProviderInfo]).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {requiresKey && (
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
                placeholder={keyConfigured ? "••••••••••••••••" : "xai-..."}
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
          )}

          {selectedModels.length > 0 && (
          <div className="space-y-1.5">
            <Label>Model</Label>
            <Select value={model} onValueChange={handleModelChange}>
              <SelectTrigger className="w-72 font-mono">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {selectedModels.map((m) => (
                  <SelectItem key={m} value={m} className="font-mono">
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          )}
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
