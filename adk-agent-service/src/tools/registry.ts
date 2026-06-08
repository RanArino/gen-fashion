/**
 * Tool Registry Pattern (M4-4)
 * Each tool an independent module registered via a registry.
 */

export class ToolRegistry {
  private tools: Map<string, any> = new Map();

  register(name: string, tool: any): void {
    this.tools.set(name, tool);
  }

  get(name: string): any {
    const tool = this.tools.get(name);
    if (!tool) {
      throw new Error(`Tool ${name} not found in registry`);
    }
    return tool;
  }

  getAll(): Map<string, any> {
    return this.tools;
  }
}

export const toolRegistry = new ToolRegistry();
