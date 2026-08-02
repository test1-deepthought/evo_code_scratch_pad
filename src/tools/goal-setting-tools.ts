/**
 * Autonomous Goal-Setting Tools for EVO
 * AGI GAP ADDRESSED: Gap 2 - Autonomous Goal-Setting (partial enhancement)
 */

import { failure, success, tool } from "./registry.ts";
import type { EvoTool } from "../types.ts";

interface KnowledgeGap { topic: string; reason: string; suggestedQuery: string; priority: "high" | "medium" | "low"; timestamp: number; }
const detectedGaps: KnowledgeGap[] = [];

function curiosityModuleTool(): EvoTool {
  return tool("curiosity_module", "Analyze tool outputs and conversation to detect knowledge gaps and promising investigation lines.", {
    context: { type: "string", description: "Recent findings to analyze for gaps." },
    focus_areas: { type: "array", items: { type: "string" }, description: "Areas of particular interest." },
    max_gaps: { type: "integer", description: "Max gaps to report (default: 5)." },
  }, ["context"], async (args) => {
    const contextText = String(args.context ?? "");
    const focusAreas = (Array.isArray(args.focus_areas) ? args.focus_areas : []).map(String);
    const maxGaps = Number(args.max_gaps ?? 5);
    if (!contextText) return failure("curiosity_module requires 'context'.");
    const gaps: KnowledgeGap[] = [];
    const questionMatches = contextText.match(/(?:unclear|unknown|uncertain|unresolved|question|what about|how does|why is|what is)([^.!?]*[?!])/gi);
    if (questionMatches) for (const match of questionMatches.slice(0, maxGaps)) gaps.push({ topic: "Unresolved Question", reason: `Detected: "${match.trim()}"`, suggestedQuery: match.trim(), priority: "high", timestamp: Date.now() });
    const exploreMatches = contextText.match(/(?:could explore|might investigate|worth looking into|further research|needs more)([^.!?]*)/gi);
    if (exploreMatches) for (const match of exploreMatches.slice(0, maxGaps)) gaps.push({ topic: "Suggested Exploration", reason: `Flagged: "${match.trim()}"`, suggestedQuery: match.trim(), priority: "medium", timestamp: Date.now() });
    if (focusAreas.length >= 2) gaps.push({ topic: "Cross-Domain Connection", reason: `Explore: ${focusAreas.join(" <-> ")}`, suggestedQuery: `relationship between ${focusAreas.join(" and ")}`, priority: "medium", timestamp: Date.now() });
    const assumptionMatches = contextText.match(/(?:assuming|assumed|if we assume|presupposing)([^.!?]*)/gi);
    if (assumptionMatches) for (const match of assumptionMatches.slice(0, 2)) gaps.push({ topic: "Verify Assumption", reason: `Test: "${match.trim()}"`, suggestedQuery: `verify: ${match.trim()}`, priority: "high", timestamp: Date.now() });
    for (const gap of gaps.slice(0, maxGaps)) detectedGaps.push(gap);
    if (detectedGaps.length > 50) detectedGaps.splice(0, detectedGaps.length - 50);
    if (!gaps.length) return success("No specific knowledge gaps detected.");
    const byP = (p: string) => gaps.filter(g => g.priority === p);
    return success([`# Knowledge Gaps (${gaps.length})`, "## HIGH PRIORITY", ...byP("high").map(g => `- **${g.topic}**: ${g.reason}\n  -> "${g.suggestedQuery}"`), "## MEDIUM PRIORITY", ...byP("medium").map(g => `- **${g.topic}**: ${g.reason}\n  -> "${g.suggestedQuery}"`), "", "[LIMITATION: These suggestions require human initiation.]"].join("\n"));
  });
}

function subGoalGeneratorTool(): EvoTool {
  return tool("sub_goal_generator", "Decompose a complex goal into smaller, actionable sub-goals with dependencies.", {
    goal: { type: "string", description: "The complex goal to decompose." },
    constraints: { type: "array", items: { type: "string" }, description: "Constraints to respect." },
    available_tools: { type: "array", items: { type: "string" }, description: "Available capabilities." },
  }, ["goal"], async (args) => {
    const goal = String(args.goal ?? "");
    const constraints = (Array.isArray(args.constraints) ? args.constraints : []).map(String);
    const tools = (Array.isArray(args.available_tools) ? args.available_tools : []).map(String);
    if (!goal) return failure("sub_goal_generator requires 'goal'.");
    const subGoals: Array<{ id: string; desc: string; deps: string[]; approach: string }> = [{ id: "understand", desc: `Define: ${goal.slice(0, 100)}`, deps: [], approach: "Research domain, define terms." }];
    const parts = goal.split(/[,;]|and|then/).filter(p => p.trim().length > 5);
    if (parts.length > 1) parts.forEach((part, i) => subGoals.push({ id: `component_${i}`, desc: `Address: ${part.trim().slice(0, 120)}`, deps: ["understand"], approach: tools.length ? `Use: ${tools.slice(0, 3).join(", ")}` : "Determine approach." }));
    else subGoals.push({ id: "solve", desc: `Solve: ${goal.slice(0, 120)}`, deps: ["understand"], approach: "Apply method from understanding phase." });
    subGoals.push({ id: "verify", desc: "Verify solution correctness", deps: subGoals.filter(s => s.id !== "understand" && s.id !== "verify").map(s => s.id), approach: "Test against constraints." }, { id: "consolidate", desc: "Synthesize results, identify remaining gaps", deps: ["verify"], approach: "Summarize learnings." });
    return success([`# Sub-Goals: ${goal.slice(0, 80)}`, constraints.length ? `\nConstraints: ${constraints.join("; ")}` : "", ...subGoals.map(sg => `### ${sg.id}\n**Goal**: ${sg.desc}\n**Depends on**: ${sg.deps.join(", ") || "(start immediately)"}\n**Approach**: ${sg.approach}`), "", "[LIMITATION: Sub-goals are suggestions. EVO cannot autonomously schedule without human prompting.]"].join("\n"));
  });
}

function investigationSuggestTool(): EvoTool {
  return tool("investigation_suggest", "Propose new investigation lines based on current session context.", {
    current_findings: { type: "string", description: "Summary of discoveries." },
    original_goal: { type: "string", description: "Original user request." },
  }, ["current_findings"], async (args) => {
    const findings = String(args.current_findings ?? "");
    const originalGoal = String(args.original_goal ?? "");
    if (!findings) return failure("investigation_suggest requires 'current_findings'.");
    const suggestions = ["**Deepen**: Explore edge cases or boundary conditions.", "**Broaden**: Connect findings to adjacent domains.", "**Challenge**: Find counterexamples or alternatives."];
    const relevantGaps = detectedGaps.filter(g => findings.toLowerCase().includes(g.topic.toLowerCase()));
    if (relevantGaps.length) { suggestions.push("**Follow up on gaps**:"); for (const gap of relevantGaps.slice(0, 3)) suggestions.push(`  - ${gap.suggestedQuery}`); }
    return success(["# Suggested Investigations", originalGoal ? `Original: ${originalGoal.slice(0, 120)}` : "", ...suggestions.map(s => `- ${s}`), "", "[LIMITATION: EVO's next turn must be human-initiated.]"].join("\n"));
  });
}

export function createGoalSettingTools(): EvoTool[] {
  return [curiosityModuleTool(), subGoalGeneratorTool(), investigationSuggestTool()];
}