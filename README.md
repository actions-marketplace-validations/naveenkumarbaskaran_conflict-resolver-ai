# Conflict Resolver AI

> 🔀 LLM-powered merge conflict detection and resolution for GitHub Actions

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Conflict%20Resolver%20AI-green?logo=github)](https://github.com/marketplace/actions/conflict-resolver-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Automatically detect, analyze, and resolve merge conflicts in your PRs using LLMs. The AI understands code semantics, intent from both branches, and resolves conflicts with explanations — not just blind `<<<<<<< HEAD` removal.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Semantic Resolution** | Understands code intent, not just text diffs |
| 🎯 **Confidence Scoring** | Each resolution rated 0-100% — only auto-resolves above threshold |
| 🔀 **Smart Strategies** | TAKE_OURS, TAKE_THEIRS, COMBINE, or full REWRITE |
| ⚡ **Auto-resolve Mode** | Commits high-confidence resolutions automatically |
| 💬 **Rich PR Comments** | Posts detailed resolution suggestions with reasoning |
| 📊 **Job Summary** | Overview table in GitHub Actions summary |
| 🔒 **Safe by Default** | Suggest-only mode — never commits without explicit opt-in |
| 🌐 **Any LLM** | OpenAI, Anthropic, Gemini, Mistral, local models via litellm |

## 🚀 Quick Start

```yaml
name: Resolve Conflicts
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  resolve:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }}
```

That's it. 3 lines of config and your PRs get intelligent conflict resolution suggestions.

## 📋 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  1. DETECT       Attempt merge, find conflict markers       │
├─────────────────────────────────────────────────────────────┤
│  2. PARSE        Extract ours/theirs/base for each block    │
├─────────────────────────────────────────────────────────────┤
│  3. ANALYZE      LLM evaluates both sides + surrounding     │
│                  context to determine intent                 │
├─────────────────────────────────────────────────────────────┤
│  4. RESOLVE      Strategy selection with confidence score   │
│                  - TAKE_OURS (one side clearly correct)      │
│                  - TAKE_THEIRS (incoming is better)          │
│                  - COMBINE (merge both additions)            │
│                  - REWRITE (neither is correct as-is)        │
├─────────────────────────────────────────────────────────────┤
│  5. APPLY        Auto-resolve if confidence ≥ threshold     │
│                  OR post suggestions as PR comment           │
└─────────────────────────────────────────────────────────────┘
```

## ⚙️ Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `api_key` | — | **Required.** API key for your LLM provider |
| `model` | `gpt-4o` | LLM model (any litellm-supported model) |
| `mode` | `suggest` | `suggest` (comment only) or `auto-resolve` (commit fixes) |
| `confidence_threshold` | `85` | Min confidence % to auto-resolve (0-100) |
| `max_conflicts` | `50` | Max conflicts to process per run |
| `extra_context` | — | Additional project context for better resolutions |
| `commit_message` | `fix: auto-resolve merge conflicts [AI]` | Commit message for auto-resolves |
| `github_token` | `${{ github.token }}` | GitHub token for PR comments and pushes |

## 📤 Outputs

| Output | Description |
|--------|-------------|
| `conflicts_found` | Total number of conflicts detected |
| `conflicts_resolved` | Number of conflicts auto-resolved |
| `confidence_avg` | Average confidence across all resolutions |
| `result_json` | Full JSON result with all conflict details |

## 📖 Usage Examples

### Suggest Only (Safe Default)

```yaml
- uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
  with:
    api_key: ${{ secrets.OPENAI_API_KEY }}
    mode: suggest
```

Posts a detailed comment with resolution suggestions. No changes to code.

### Auto-resolve High Confidence

```yaml
- uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
  with:
    api_key: ${{ secrets.OPENAI_API_KEY }}
    mode: auto-resolve
    confidence_threshold: 90
```

Automatically commits resolutions with ≥90% confidence. Lower ones posted as suggestions.

### Use Claude for Better Reasoning

```yaml
- uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
  with:
    api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    model: anthropic/claude-sonnet-4-20250514
    mode: auto-resolve
    confidence_threshold: 85
```

### With Project Context

```yaml
- uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
  with:
    api_key: ${{ secrets.OPENAI_API_KEY }}
    extra_context: |
      This is a TypeScript monorepo using pnpm workspaces.
      Prefer named exports over default exports.
      Use strict TypeScript with no `any` types.
```

### Block PR on Unresolved Conflicts

```yaml
- uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
  id: conflicts
  with:
    api_key: ${{ secrets.OPENAI_API_KEY }}

- name: Fail if conflicts remain
  if: steps.conflicts.outputs.conflicts_found > steps.conflicts.outputs.conflicts_resolved
  run: |
    echo "::error::Unresolved merge conflicts require manual attention"
    exit 1
```

### Trigger on Merge Queue

```yaml
name: Resolve on Merge Queue
on:
  merge_group:

jobs:
  resolve:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: naveenkumarbaskaran/conflict-resolver-ai@v0.1.0
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }}
          mode: auto-resolve
          confidence_threshold: 95
```

## 🧠 Resolution Strategies

| Strategy | When Used | Example |
|----------|-----------|---------|
| **TAKE_OURS** | Current branch has the correct/newer version | Dependency version bump on main |
| **TAKE_THEIRS** | Incoming branch is clearly the improvement | New feature replaces old implementation |
| **COMBINE** | Both sides add non-overlapping changes | Two new imports, two new functions |
| **REWRITE** | Neither side is correct alone, needs synthesis | Interface changes affecting both additions |
| **MANUAL** | Too risky/ambiguous for AI to decide | Business logic conflicts, semantic ambiguity |

## 🔒 Security

- API keys are passed via secrets — never logged
- `suggest` mode makes zero changes to your code
- `auto-resolve` mode requires explicit opt-in + high confidence threshold
- All resolutions include confidence scores and reasoning for audit
- Git commits are attributed to the GitHub Actions bot

## 🤝 Works With

- **Any language** — LLM understands code semantics regardless of language
- **Any LLM provider** — OpenAI, Anthropic, Google, Mistral, Ollama, Azure, AWS Bedrock
- **Monorepos** — Handles conflicts across multiple packages/services
- **Any branch strategy** — main/develop, trunk-based, release branches

## 📊 Example Output

After running, you'll see a PR comment like:

> ## 🔀 Conflict Resolver AI
>
> Found **3 conflict(s)** across 2 file(s)
>
> | Metric | Value |
> |--------|-------|
> | Total Conflicts | 3 |
> | Auto-resolvable (≥85%) | 2 |
> | Needs Human Review | 1 |
> | Avg Confidence | 82% |
>
> ### Resolution Details
> <details><summary>🔀 src/config.ts (line ~24) — COMBINE 🟢 92%</summary>
> Both branches add new config keys. Combined both additions in alphabetical order.
> </details>

## License

MIT — see [LICENSE](LICENSE)
