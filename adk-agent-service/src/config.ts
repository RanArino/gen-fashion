export const config = {
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || "",
  agentModel: process.env.AGENT_MODEL || "gemini-2.0-flash",
  fastApiServiceUrl: process.env.FASTAPI_SERVICE_URL || "http://localhost:8000",
};
