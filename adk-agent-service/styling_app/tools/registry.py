"""Tool Registry (M4-4, req §7.2).

Every tool is an independent module that registers its function here by name;
agents pull their toolsets from the registry instead of importing tool
functions directly, keeping per-sub-agent toolsets separable (ADL-019).
"""

from typing import Callable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = fn

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def all(self) -> dict[str, Callable]:
        return dict(self._tools)


registry = ToolRegistry()
