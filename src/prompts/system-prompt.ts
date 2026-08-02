const referenceDate = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  year: "numeric",
  month: "long",
  day: "2-digit",
}).format(new Date());

export const EVO_SYSTEM_PROMPT = "You are EVO (Explicit-assumption Verification Orchestrator), an autonomous evidence-based AI agent. Match the reasoning method, tools, and verification effort to the user's requested outcome.";

export function responseTemplate(tier: string): string {
  if (tier === "MATHS") {
    return ["## Direct Answer", "## Status", "## Problem Model", "## Mathematical Argument", "## Verification", "## Assumptions Used"].join("\\n");
  }
  if (tier === "CODE") {
    return "No fixed CODE template. Lead with the requested outcome and use natural structure.";
  }
  return ["## Direct Answer", "## Status", "## Problem Specification", "## Derived Conclusions", "## Assumptions Used", "## Dependence Classification", "## Validation Report"].join("\\n");
}
