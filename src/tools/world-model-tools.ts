/**
 * Persistent World-Model Tools for EVO
 * AGI GAP ADDRESSED: Gap 1 - Persistent World-Model
 */

import { failure, success, tool } from "./registry.ts";
import type { EvoTool } from "../types.ts";
import { createHash, randomUUID } from "node:crypto";
import { writeFile, readFile, mkdir } from "node:fs/promises";

export interface EpisodicMemory {
  id: string; timestamp: number; turn: number;
  event: string; outcome: string; lessons: string[];
  tags: string[]; importance: number;
}

class EpisodicMemoryStore {
  private memories: EpisodicMemory[] = [];
  private persistPath: string | null = null;
  constructor(persistPath?: string) { this.persistPath = persistPath ?? null; }
  async load(): Promise<void> {
    if (!this.persistPath) return;
    try { const data = await readFile(this.persistPath, "utf8"); this.memories = JSON.parse(data); } catch { this.memories = []; }
  }
  async save(): Promise<void> {
    if (!this.persistPath) return;
    try { const dir = this.persistPath.split("/").slice(0, -1).join("/"); await mkdir(dir, { recursive: true }).catch(() => {}); await writeFile(this.persistPath, JSON.stringify(this.memories, null, 2)); } catch {}
  }
  add(memory: EpisodicMemory): void { this.memories.push(memory); if (this.memories.length > 500) this.memories = this.memories.slice(-500); }
  search(query: string, maxResults = 10): EpisodicMemory[] {
    const lower = query.toLowerCase();
    return this.memories.map(m => {
      let score = 0;
      if (m.event.toLowerCase().includes(lower)) score += 3;
      if (m.outcome.toLowerCase().includes(lower)) score += 2;
      for (const lesson of m.lessons) if (lesson.toLowerCase().includes(lower)) score += 2;
      for (const tag of m.tags) if (tag.toLowerCase().includes(lower)) score += 1;
      return { memory: m, score };
    }).filter(({ score }) => score > 0).sort((a, b) => b.score - a.score).slice(0, maxResults).map(({ memory }) => memory);
  }
  recent(limit = 20): EpisodicMemory[] { return this.memories.slice(-limit).reverse(); }
  byTag(tag: string): EpisodicMemory[] { return this.memories.filter(m => m.tags.includes(tag)).reverse(); }
  count(): number { return this.memories.length; }
}

const globalMemoryStore = new EpisodicMemoryStore();
function setEpisodicMemoryPath(path: string): void { (globalMemoryStore as unknown as Record<string, unknown>).persistPath = path; }
async function loadEpisodicMemoryFromPath(): Promise<void> { await globalMemoryStore.load(); }

function sessionSummarizeTool(): EvoTool {
  return tool("session_summarize", "Consolidate current session findings into a structured summary for cross-session continuity.", {
    topics: { type: "array", items: { type: "string" }, description: "Key topics covered." },
    decisions: { type: "array", items: { type: "string" }, description: "Decisions reached." },
    open_questions: { type: "array", items: { type: "string" }, description: "Unresolved questions." },
    key_insights: { type: "array", items: { type: "string" }, description: "Important insights." },
    tags: { type: "array", items: { type: "string" }, description: "Categorization tags." },
  }, [], async (args) => {
    const topics = (Array.isArray(args.topics) ? args.topics : []).map(String);
    const decisions = (Array.isArray(args.decisions) ? args.decisions : []).map(String);
    const openQuestions = (Array.isArray(args.open_questions) ? args.open_questions : []).map(String);
    const keyInsights = (Array.isArray(args.key_insights) ? args.key_insights : []).map(String);
    const tags = (Array.isArray(args.tags) ? args.tags : []).map(String);
    const now = new Date().toISOString();
    const sections = [
      `# Session Summary - ${now}`,
      topics.length ? `## Topics\n${topics.map(t => `- ${t}`).join("\n")}` : "",
      decisions.length ? `## Decisions\n${decisions.map(d => `- ${d}`).join("\n")}` : "",
      keyInsights.length ? `## Key Insights\n${keyInsights.map(i => `- ${i}`).join("\n")}` : "",
      openQuestions.length ? `## Open Questions\n${openQuestions.map(q => `- ${q}`).join("\n")}` : "",
      tags.length ? `## Tags\n${tags.join(", ")}` : "",
    ].filter(Boolean);
    const summary = sections.join("\n");
    const hash = createHash("sha256").update(summary).digest("hex").slice(0, 16);
    globalMemoryStore.add({ id: `session-${now.slice(0, 10)}-${hash}`, timestamp: Date.now(), turn: 0, event: `Session: ${topics.slice(0, 3).join(", ") || "general"}`, outcome: decisions.join("; ") || "No decisions", lessons: keyInsights, tags, importance: 7 });
    await globalMemoryStore.save();
    return success(`${summary}\n\n[Memory ID: ${hash}] [Total: ${globalMemoryStore.count()}]`);
  });
}

function episodicMemoryTool(): EvoTool {
  return tool("episodic_memory", "Search, record, and retrieve episodic memories across sessions.", {
    action: { type: "string", enum: ["search", "recent", "record", "by_tag", "stats"] },
    query: { type: "string", description: "Search query or tag name." },
    event: { type: "string", description: "For record: what happened." },
    outcome: { type: "string", description: "For record: result." },
    lessons: { type: "array", items: { type: "string" }, description: "For record: lessons." },
    tags: { type: "array", items: { type: "string" }, description: "For record: tags." },
    importance: { type: "integer", description: "For record: 1-10 (default: 5)." },
    max_results: { type: "integer", description: "Max results (default: 10)." },
  }, ["action"], async (args) => {
    const action = String(args.action ?? "");
    if (action === "record") {
      const mem: EpisodicMemory = { id: randomUUID(), timestamp: Date.now(), turn: 0, event: String(args.event ?? ""), outcome: String(args.outcome ?? ""), lessons: Array.isArray(args.lessons) ? args.lessons.map(String) : [], tags: Array.isArray(args.tags) ? args.tags.map(String) : [], importance: Math.min(10, Math.max(1, Number(args.importance ?? 5))) };
      if (!mem.event) return failure("record requires 'event'.");
      globalMemoryStore.add(mem); await globalMemoryStore.save();
      return success(`Recorded: ${mem.id} | Total: ${globalMemoryStore.count()}`);
    }
    if (action === "search") { const q = String(args.query ?? ""); if (!q) return failure("search requires 'query'."); const results = globalMemoryStore.search(q, Number(args.max_results ?? 10)); if (!results.length) return success(`No memories for: ${q}`); return success(results.map(m => `[${m.id}] (${m.importance}/10) ${m.event} -> ${m.outcome.slice(0, 150)}\n  Lessons: ${m.lessons.join("; ") || "none"}\n  Tags: ${m.tags.join(", ")}`).join("\n\n")); }
    if (action === "recent") { const results = globalMemoryStore.recent(Number(args.max_results ?? 10)); if (!results.length) return success("No memories yet."); return success(results.map(m => `[${m.id}] ${m.event} -> ${m.outcome.slice(0, 100)}`).join("\n")); }
    if (action === "by_tag") { const tag = String(args.query ?? ""); if (!tag) return failure("by_tag requires 'query' (tag name)."); const results = globalMemoryStore.byTag(tag); if (!results.length) return success(`No memories tagged: ${tag}`); return success(results.map(m => `[${m.id}] ${m.event} -> ${m.outcome.slice(0, 100)}`).join("\n")); }
    if (action === "stats") return success(`Total memories: ${globalMemoryStore.count()}`);
    return failure(`Unknown action: ${action}`);
  });
}

interface Belief { belief: string; confidence: string; source: string; timestamp: number; }
const beliefStore: Belief[] = [];

function beliefStateTool(): EvoTool {
  return tool("belief_state", "Track EVO's beliefs: assert, retract, query, and maintain a consistent world model.", {
    action: { type: "string", enum: ["assert", "retract", "query", "list"] },
    belief: { type: "string", description: "Belief statement." },
    confidence: { type: "string", enum: ["certain", "likely", "uncertain", "speculative"] },
    source: { type: "string", description: "Source." },
    query: { type: "string", description: "Substring to search." },
  }, ["action"], async (args) => {
    const action = String(args.action ?? "");
    if (action === "assert") { const b = String(args.belief ?? ""); if (!b) return failure("assert requires 'belief'."); beliefStore.push({ belief: b, confidence: String(args.confidence ?? "uncertain"), source: String(args.source ?? "observation"), timestamp: Date.now() }); if (beliefStore.length > 200) beliefStore.splice(0, beliefStore.length - 200); return success(`Asserted (${beliefStore.length} total): ${b.slice(0, 200)}`); }
    if (action === "retract") { const q = String(args.query ?? "").toLowerCase(); if (!q) return failure("retract requires 'query'."); const before = beliefStore.length; const filtered = beliefStore.filter(b2 => !b2.belief.toLowerCase().includes(q)); beliefStore.length = 0; beliefStore.push(...filtered); return success(`Retracted ${before - filtered.length} belief(s).`); }
    if (action === "query") { const q = String(args.query ?? "").toLowerCase(); if (!q) return failure("query requires 'query'."); const matches = beliefStore.filter(b2 => b2.belief.toLowerCase().includes(q)); if (!matches.length) return success(`No beliefs matching: ${q}`); return success(matches.map(b2 => `[${b2.confidence}] ${b2.belief} (source: ${b2.source})`).join("\n")); }
    if (action === "list") { if (!beliefStore.length) return success("No beliefs."); return success(beliefStore.map(b2 => `[${b2.confidence}] ${b2.belief.slice(0, 200)}`).join("\n")); }
    return failure(`Unknown action: ${action}`);
  });
}

function crossSessionKnowledgeTool(): EvoTool {
  return tool("cross_session_knowledge", "Retrieve knowledge from previous sessions across restarts.", {
    query: { type: "string", description: "What to search for." },
    max_results: { type: "integer", description: "Max results (default: 10)." },
  }, ["query"], async (args) => {
    const query = String(args.query ?? ""); const maxResults = Number(args.max_results ?? 10);
    if (!query) return failure("cross_session_knowledge requires 'query'.");
    const memoryResults = globalMemoryStore.search(query, maxResults);
    const beliefMatches = beliefStore.filter(b => b.belief.toLowerCase().includes(query.toLowerCase())).slice(0, maxResults);
    const parts: string[] = [];
    if (memoryResults.length) { parts.push("## Episodic Memories", ...memoryResults.map(m => `- [${m.id}] ${m.event} -> ${m.outcome.slice(0, 150)} (importance: ${m.importance}/10)`)); }
    if (beliefMatches.length) { parts.push("## Related Beliefs", ...beliefMatches.map(b => `- [${b.confidence}] ${b.belief.slice(0, 200)}`)); }
    if (!parts.length) return success(`No knowledge for: ${query}`);
    return success(parts.join("\n"));
  });
}

export interface WorldModelConfig { memoryPersistPath?: string; }

export function createWorldModelTools(config: WorldModelConfig = {}): EvoTool[] {
  if (config.memoryPersistPath) setEpisodicMemoryPath(config.memoryPersistPath);
  void loadEpisodicMemoryFromPath();
  return [sessionSummarizeTool(), episodicMemoryTool(), beliefStateTool(), crossSessionKnowledgeTool()];
}