# AI Agent Instructions

These instructions apply to all repositories under `/Users/ran/my-app` unless a deeper `AGENTS.md` in a child repository overrides them. Each child repository is expected to manage one application or service. Keep shared guidance here generic; put stack-specific commands, architecture rules, and service ownership details in the child repository.

## Purpose

AI agents working under this directory should help engineers deliver small, working changes with clear verification. The default behavior is to understand the target repository, make the minimal useful edit, run the relevant checks, and document what changed.

## Operating Principles

- State assumptions explicitly when they affect implementation.
- Ask before guessing when a request is materially ambiguous or risky.
- Prefer the simplest change that satisfies the request.
- Keep edits surgical. Do not refactor unrelated code or reformat files incidentally.
- Match the local style, tools, and conventions of the target repository.
- Favor readable, boring code over clever abstractions.
- Remove imports, variables, files, and branches that become unused because of your change.
- Leave pre-existing unrelated problems alone, but mention them separately when useful.
- Treat plans as living documents when the work is plan-driven.

## Repository Discovery

Before editing a child repository, inspect enough context to identify its conventions:

1. Read the nearest `AGENTS.md`, `README.md`, package or module manifests, and relevant docs.
2. Identify the stack, test commands, build commands, and generated-code workflow.
3. Search for existing implementations that resemble the requested change.
4. Define success in observable terms before implementing.

Use fast local search tools such as `rg` and `rg --files` when available.

## Planning

Use an ExecPlan when the work is multi-step, risky, cross-cutting, or explicitly requested. ExecPlans must follow `PLANS.md` in this directory unless a child repository has its own `PLANS.md`.

When work relates to any requirement tracked in `feature-matrix-**.md`, keep the feature matrix synchronized:

- Update the relevant `feature-matrix-**.md` whenever work starts, is planned with an ExecPlan, or is completed for a tracked requirement.
- If an ExecPlan targets a requirement marked `❌ Not yet implemented`, change that requirement to `🟡 In progress` in the same change as the plan.
- When creating or updating an ExecPlan from `feature-matrix-**.md`, synchronize the matrix before finishing the turn, including status icons, notes, and summary counts.

For small, single-purpose edits, a short working plan is enough:

```text
1. Inspect the relevant files -> verify: identify current behavior and local style.
2. Implement the minimal change -> verify: review the diff.
3. Run checks -> verify: tests/build/lint pass or failures are documented.
```

## Implementation

- Make the smallest coherent change.
- Prefer local helpers and established patterns over new abstractions.
- Do not add configurability, framework dependencies, or new layers unless the request requires them.
- Keep flows shallow and names descriptive.
- Add comments only when they explain non-obvious intent or constraints.
- Do not modify generated files unless the repository's workflow expects them to be committed.
- Do not modify shared instructions, CI configuration, or broad repo policy unless asked.

## Verification

Run the checks appropriate to the child repository. Discover exact commands from the repository itself rather than assuming a universal toolchain.

Common examples include:

- JavaScript or TypeScript: `npm test`, `npm run lint`, `npm run build`
- Python: `pytest`, `ruff`, `mypy`
- Go: `go test ./...`, `go build ./...`
- Rust: `cargo test`, `cargo clippy`, `cargo build`

If a check cannot be run because dependencies, services, credentials, or network access are unavailable, record that limitation and explain what was verified instead.

## Documentation

Update documentation when behavior, commands, setup, APIs, configuration, or operational expectations change. Do not update docs for purely internal edits unless the existing docs would become wrong.

## Safety

- Do not run destructive commands unless explicitly requested or approved.
- Do not force-push protected branches.
- Do not overwrite user changes.
- Do not access external network resources unless required for the task and allowed by the environment.
- Do not change core operating files or repository-wide instructions unless the user asks.
- Keep secrets out of logs, plans, commits, and documentation.

## Commits

When asked to commit, use Conventional Commits:

```text
<type>(<scope>): <short summary>
```

Common types are `feat`, `fix`, `docs`, `refactor`, `test`, `build`, and `chore`. Choose a scope that matches the child repository or feature area.

## Child Repository Overrides

A child repository may define its own `AGENTS.md` with more specific rules. The nearest `AGENTS.md` to the files being edited takes precedence. Use this top-level file only for behavior that should remain true across all applications and services under `/Users/ran/my-app`.
