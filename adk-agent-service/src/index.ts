import { createServer } from "http";
import { config } from "./config";
import { StylingOrchestratorAgent } from "./agents";

const PORT = 3000;

async function main() {
  console.log(`ADK Agent Service starting with AGENT_MODEL=${config.agentModel}`);

  const orchestrator = new StylingOrchestratorAgent();
  console.log("Orchestrator agent initialized");

  const server = createServer((req, res) => {
    if (req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok" }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  server.listen(PORT, () => {
    console.log(`ADK Agent Service listening on port ${PORT}`);
  });

  process.on("SIGTERM", () => {
    server.close(() => process.exit(0));
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
