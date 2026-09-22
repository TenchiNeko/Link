"""
Configuration for the standalone orchestrator.

 v0.8.0: Dual local-model endpoint architecture.
  - A primary endpoint handles planning and build work.
  - A secondary endpoint can handle lightweight initialization, exploration, and tests.
  - No model swapping is required when both endpoints are available.
  - An optional knowledge-base service can be configured separately.

Defines model routing via direct Ollama/API HTTP endpoints.
No CLI tool dependencies.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class ModelConfig:
    """Configuration for a model endpoint."""
    name: str
    provider: str  # "ollama" or "anthropic"
    model_id: str
    endpoint: Optional[str] = None  # HTTP base URL for ollama
    api_key_env: Optional[str] = None  # env var name for API key
    temperature: float = 0.0
    max_tokens: int = 16384
    context_window: int = 131072  # total context window in tokens (default 128K for Llama 3.3)
    supports_tools: bool = True  # whether model handles tool_call format
    native_tool_calling: bool = False  # True = model returns structured tool_calls natively (Qwen3, Llama 3.3)
    tool_call_style: str = "text"  # "text" = parse from content, "native" = use Ollama tool_calls field

    # v1.2: Inference optimization fields
    repeat_penalty: float = 1.0  # 1.0=disabled. Qwen-Next is very sensitive to penalties (Stepfunction/r/LocalLLaMA)
    thinking_mode: str = "auto"  # "enabled"=always /think, "disabled"=always /no_think, "auto"=per-agent
    thinking_budget: int = 8192  # max thinking tokens (0=unlimited). Qwen3 native budget control
    num_keep: int = -1  # tokens to keep from initial prompt for KV cache (-1=auto)
    top_p: float = 0.95  # nucleus sampling (Qwen recommended)
    min_p: float = 0.0  # min-p sampling (0=disabled)
    draft_model: Optional[str] = None  # speculative decoding draft model (Ollama server-side config)


@dataclass
class AgentConfig:
    """Configuration for a specific agent role."""
    role: str
    model: ModelConfig
    system_prompt_file: Optional[str] = None
    timeout_seconds: int = 600
    retry_count: int = 2
    max_tool_rounds: int = 50  # max tool-use round trips per invocation


@dataclass
class Config:
    """Main configuration container."""
    max_iterations: int = 3
    plan_dir: str = ".agents/plans"
    report_dir: str = ".agents/reports"
    log_dir: str = ".agents/logs"
    kb_url: str = "http://localhost:8787"  # v0.8.0: RAG Knowledge Base server
    librarian_model: Optional['ModelConfig'] = None  # v0.9.0: Librarian curator model
    experiencer_model: Optional['ModelConfig'] = None  # v1.3: Dedicated personality experiencer
    agents: Dict[str, AgentConfig] = field(default_factory=dict)

    def get_agent(self, role: str) -> AgentConfig:
        if role not in self.agents:
            raise ValueError(f"Unknown agent role: {role}")
        return self.agents[role]

    @staticmethod
    def load_default() -> "Config":
        """Create default config for local Ollama setup."""
        return default_config()


def default_config() -> Config:
    """
    Default configuration using local Ollama endpoints.

    The defaults intentionally use loopback endpoints. Deployment-specific hosts,
    models, ports, and hardware belong in local environment configuration rather
    than in source control.
    """

    # --- Model definitions ---

    # PRIMARY (Instance 1, port 11434): Qwen2.5-Coder 32B — heavy reasoning
    llama_70b = ModelConfig(
        name="Qwen2.5-Coder 32B (primary local endpoint)",
        provider="openai",
        endpoint=os.environ.get("OLLAMA_PRIMARY_URL", "http://127.0.0.1:8090"),
        model_id="qwen-agent.gguf",
        temperature=0.0,
        max_tokens=16384,
        context_window=32768,  # 128K context
        supports_tools=True,
        # v1.2: Inference optimizations
        repeat_penalty=1.0,  # DISABLED — Qwen-Next very sensitive (Stepfunction/r/LocalLLaMA)
        thinking_mode="auto",  # Per-agent: enabled for plan/build, disabled for fast tasks
        thinking_budget=0,  # 0=unlimited thinking for heavy reasoning
        top_p=0.95,
    )

    # SECONDARY: a smaller local model for fast agent work.
    qwen_14b = ModelConfig(
        name="Qwen 2.5 Coder 14B (secondary local endpoint)",
        provider="openai",
        endpoint=os.environ.get("OLLAMA_PRIMARY_URL", "http://127.0.0.1:8090"),
        model_id="qwen-agent.gguf",
        temperature=0.0,
        max_tokens=16384,
        context_window=32768,  # 32K context
        supports_tools=True,
        # v1.2: Inference optimizations
        repeat_penalty=1.0,  # DISABLED for Qwen family
        thinking_mode="disabled",  # Fast agent — no extended reasoning
    )

    qwen_14b_testgen = ModelConfig(
        name="Qwen 2.5 Coder 14B LoRA Test-Gen (secondary local endpoint)",
        provider="openai",
        endpoint=os.environ.get("OLLAMA_PRIMARY_URL", "http://127.0.0.1:8090"),
        model_id="qwen-agent.gguf",
        temperature=0.3,
        max_tokens=16384,
        context_window=32768,
        supports_tools=True,
        # v1.2: Inference optimizations
        repeat_penalty=1.0,
        thinking_mode="disabled",  # Test gen doesn't need extended reasoning
    )

    # --- Qwen3 alternatives (native tool calling) ---
    # Uncomment and swap into agent assignments when available.

    # Qwen3 30B-A3B (MoE, only 3B active)
    # qwen3_30b = ModelConfig(
    #     name="Qwen3 30B-A3B (local)",
    #     provider="openai",
    #     endpoint=os.environ.get("OLLAMA_PRIMARY_URL", "http://127.0.0.1:8090"),
    #     model_id="qwen-agent.gguf",
    #     temperature=0.0,
    #     max_tokens=16384,
    #     context_window=32768,
    #     supports_tools=True,
    #     native_tool_calling=True,
    #     tool_call_style="native",
    # )

    # --- Agent role assignments ---
    # Primary endpoint: plan + build — best reasoning for code generation.
    # Secondary endpoint: initializer + explore + test — fast, lightweight work.

    # v0.9.0: Librarian model — uses Instance 2 (same as init/explore/test)
    # Runs post-session curation: error patterns, journal entries, code snippets.
    # Can also point to another endpoint by changing the local configuration.
    librarian_model = ModelConfig(
        name="Qwen3.5-35B-A3B Q8 (llama.cpp Integrator)",
        provider="openai",
        endpoint="http://127.0.0.1:8090",
        model_id="qwen-agent.gguf",
        temperature=0.1,
        max_tokens=16384,
        context_window=8192,
        supports_tools=False,
        top_p=0.95,
    )


    # QWEN3.5 (llama.cpp, port 8000): Qwen3.5-35B-A3B Q8 — personality experiencer
    qwen35_experiencer = ModelConfig(
        name="Qwen3.5-35B-A3B Q8 (llama.cpp)",
        provider="openai",
        endpoint="http://127.0.0.1:8090",
        model_id="qwen-agent.gguf",
        temperature=0.6,
        max_tokens=16384,
        context_window=8192,
        supports_tools=False,
        top_p=0.95,
    )


    # OPENROUTER BIG MODEL: optional remote fallback / pipeline expansion model
    openrouter_big_model = ModelConfig(
        name="OpenRouter DeepSeek V4 Pro",
        provider="openai",
        endpoint=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api"),
        model_id=os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-coder"),
        temperature=0.0,
        max_tokens=32768,
        context_window=131072,
        supports_tools=False,
        top_p=0.95,
    )

    agents = {
        "initializer": AgentConfig(
            role="initializer",
            model=llama_70b,
            system_prompt_file="prompts/initializer.txt",
            timeout_seconds=1800,
            max_tool_rounds=4,
        ),
        "explore": AgentConfig(
            role="explore",
            model=llama_70b,
            system_prompt_file="prompts/explore.txt",
            timeout_seconds=1800,
        ),
        "plan": AgentConfig(
            role="plan",
            model=openrouter_big_model,
            system_prompt_file="prompts/plan.txt",
            timeout_seconds=1800,
        ),
        "build": AgentConfig(
            role="build",
            model=llama_70b,
            system_prompt_file="prompts/build.txt",
            timeout_seconds=1800,
            max_tool_rounds=25,
        ),
        "test": AgentConfig(
            role="test",
            model=openrouter_big_model,
            system_prompt_file="prompts/test.txt",
            timeout_seconds=1800,
            max_tool_rounds=40,
        ),
        "test_gen": AgentConfig(
            role="test_gen",
            model=llama_70b,
            system_prompt_file="prompts/test_gen.txt",
            timeout_seconds=1800,
            max_tool_rounds=25,
        ),
    }

    return Config(
        max_iterations=3,
        kb_url=os.environ.get("KB_URL", "http://localhost:8787"),
        librarian_model=librarian_model,
        experiencer_model=qwen35_experiencer,
        agents=agents,
    )


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load config from JSON file, falling back to defaults."""
    config = default_config()

    if config_path and config_path.exists():
        with open(config_path) as f:
            overrides = json.load(f)

        if "max_iterations" in overrides:
            config.max_iterations = overrides["max_iterations"]

        if "kb_url" in overrides:
            config.kb_url = overrides["kb_url"]

        if "agents" in overrides:
            for role, ao in overrides["agents"].items():
                if role in config.agents:
                    agent = config.agents[role]
                    if "model" in ao:
                        agent.model.model_id = ao["model"]
                    if "provider" in ao:
                        agent.model.provider = ao["provider"]
                    if "endpoint" in ao:
                        agent.model.endpoint = ao["endpoint"]
                    if "timeout" in ao:
                        agent.timeout_seconds = ao["timeout"]
                    if "supports_tools" in ao:
                        agent.model.supports_tools = ao["supports_tools"]
                    if "native_tool_calling" in ao:
                        agent.model.native_tool_calling = ao["native_tool_calling"]
                    if "tool_call_style" in ao:
                        agent.model.tool_call_style = ao["tool_call_style"]
                    if "max_tool_rounds" in ao:
                        agent.max_tool_rounds = ao["max_tool_rounds"]
                    if "context_window" in ao:
                        agent.model.context_window = ao["context_window"]
                    # v1.2: Inference optimization overrides
                    if "repeat_penalty" in ao:
                        agent.model.repeat_penalty = ao["repeat_penalty"]
                    if "thinking_mode" in ao:
                        agent.model.thinking_mode = ao["thinking_mode"]
                    if "thinking_budget" in ao:
                        agent.model.thinking_budget = ao["thinking_budget"]
                    if "top_p" in ao:
                        agent.model.top_p = ao["top_p"]
                    if "min_p" in ao:
                        agent.model.min_p = ao["min_p"]

    return config

# Admin/supervisor role configuration.
# Phase 1: role exists but is not allowed to edit code or run shell commands.
ORCH_ADMIN_MODE = False
ORCH_ADMIN_MODEL = ""
ORCH_ADMIN_PROVIDER = ""
ORCH_ADMIN_CAN_WRITE = False
ORCH_ADMIN_CAN_RUN_SHELL = False
