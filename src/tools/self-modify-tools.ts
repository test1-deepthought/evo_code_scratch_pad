/**
 * Architectural Self-Modification Tools for EVO
 * AGI GAP ADDRESSED: Gap 4 - Architectural Self-Modification (partial)
 */

import { failure, success, tool } from "./registry.ts";
import type { EvoTool } from "../types.ts";
import { createHash } from "node:crypto";

interface CodeProposal { id: string; timestamp: number; target: string; change: string; rationale: string; risk: "low" | "medium" | "high"; status: "proposed" | "applied" | "rejected"; }
const proposals: CodeProposal[] = [];

function codeProposalTool(): EvoTool {
  return tool("code_proposal", "Propose a code change to EVO's source for human review. NOT automatically applied.", {
    target: { type: "string", description: "Component to change." },
    change: { type: "string", description: "Description of the change." },
    rationale: { type: "string", description: "Why this improves EVO." },
    code_snippet: { type: "string", description: "Optional: exact code." },
  }, ["target", "change", "rationale"], async (args) => {
    const target = String(args.target ?? ""); const change = String(args.change ?? ""); const rationale = String(args.rationale ?? ""); const snippet = String(args.code_snippet ?? "");
    if (!target || !change || !rationale) return failure("code_proposal requires target, change, rationale.");
    let risk: CodeProposal["risk"] = "medium";
    if (target.includes("prompt") || target.includes("tool")) risk = "low";
    if (target.includes("agent") || target.includes("workflow")) risk = "high";
    const proposal: CodeProposal = { id: createHash("sha256").update(`${target}:${change}:${Date.now()}`).digest("hex").slice(0, 12), timestamp: Date.now(), target, change, rationale, risk, status: "proposed" };
    proposals.push(proposal);
    if (proposals.length > 100) proposals.splice(0, proposals.length - 100);
    return success([`# Proposal ${proposal.id}`, `**Target**: ${target} | **Risk**: ${risk.toUpperCase()}`, `**Change**: ${change}`, `**Rationale**: ${rationale}`, snippet ? `\n**Code**:\n\`\`\`\n${snippet}\n\`\`\`` : "", `\n[STATUS: PROPOSED - NOT applied. Requires human review.]`, "[LIMITATION: EVO cannot self-modify.]"].join("\n"));
  });
}

function architectureIntrospectTool(): EvoTool {
  return tool("architecture_introspect", "Report on EVO's architecture: extension points and modification boundaries.", {
    aspect: { type: "string", enum: ["tools", "extension_points", "modification_boundaries", "all"] },
  }, ["aspect"], async () => {
    const extensionPoints = ["Tool Registry: Add tools via register()/replace().", "System Prompt: Edit text, add instructions.", "Config: Model, API keys, timeouts.", "Subagent Pool: Add subagent types.", "Session Knowledge: Extend memory.", "Evidence Ledger: Extend tracking."];
    const boundaries = ["SAFE (tool extensions): prompt text, config, tool definitions.", "DO NOT MODIFY: REASON preflight loop, ToolRegistry.execute(), EvoAgent.thinkInternal().", "REASON: Core orchestration is deterministic for reliability."];
    return success(["# EVO Architecture", "## Extension Points", ...extensionPoints.map(e => `- ${e}`), "## Modification Boundaries", ...boundaries.map(b => `- ${b}`), "## Proposals", proposals.length ? proposals.map(p => `- [${p.id}] ${p.target}: ${p.change.slice(0, 80)}`).join("\n") : "None."].join("\n"));
  });
}

function safeModificationBoundaryTool(): EvoTool {
  return tool("safe_modification_boundary", "Document safe vs unsafe modification areas.", { target: { type: "string", description: "Component to check." } }, [], async (args) => {
    const target = String(args.target ?? "");
    const boundaries: Record<string, { safe: string[]; unsafe: string[]; reason: string }> = {
      tool_registry: { safe: ["Add tools", "Replace implementations"], unsafe: ["Modify dispatch", "Change schema"], reason: "Security boundary between LLM and system." },
      system_prompt: { safe: ["Edit text", "Add instructions"], unsafe: ["Remove verification", "Alter routing"], reason: "Behavioral contract." },
      agent_loop: { safe: ["Add callbacks", "Extend logging"], unsafe: ["Modify thinkInternal()", "Bypass gates"], reason: "Deterministic reliability core." },
    };
    if (target && boundaries[target]) { const b = boundaries[target]; return success(`# ${target}\n## SAFE\n${b.safe.map(s => `- ${s}`).join("\n")}\n## UNSAFE\n${b.unsafe.map(s => `- ${s}`).join("\n")}\n**Why**: ${b.reason}`); }
    return success(["# Modification Boundaries", ...Object.entries(boundaries).map(([k, b]) => `## ${k}\nSAFE: ${b.safe.join("; ")}\nUNSAFE: ${b.unsafe.join("; ")}`), "\nRule: anything a TOOL can do is safe. Core loop changes require fundamental architectural change."].join("\n"));
  });
}

export function createSelfModifyTools(): EvoTool[] {
  return [codeProposalTool(), architectureIntrospectTool(), safeModificationBoundaryTool()];
}