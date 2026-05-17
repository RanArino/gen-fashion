export const config = {
  googleGenaiApiKey: process.env.GOOGLE_GENAI_API_KEY || "",
  agentModel: process.env.AGENT_MODEL || "gemini-2.0-flash",
  fastApiServiceUrl: process.env.FASTAPI_SERVICE_URL || "http://localhost:8000",
};
