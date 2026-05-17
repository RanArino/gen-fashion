import { config } from "./config";
import { StylingOrchestratorAgent } from "./agents";

console.log(`ADK Agent Service starting with AGENT_MODEL=${config.agentModel}`);

export async function main() {
  const orchestrator = new StylingOrchestratorAgent();
  console.log("Orchestrator agent initialized");
}

main().catch(console.error);
