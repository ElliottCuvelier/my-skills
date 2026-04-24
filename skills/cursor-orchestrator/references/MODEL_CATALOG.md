# Model Catalog

Fetched at: 2026-04-24T09:17:00Z
Source: https://cursor.com/docs/models-and-pricing.md

## Selected tiers

| Tier | Model | Provider | Input $/Mtok | Output $/Mtok | Notes |
| --- | --- | --- | --- | --- | --- |
| `composer` | Composer 2 | Cursor | $0.5 | $2.5 | Best price/performance default for most implementation work. |
| `fast` | Cursor fast tier | Cursor | — | — | Cheapest Cursor tier — good for trivial edits and high-volume grunt work. |
| `mini` | GPT-5.4 Nano | OpenAI | $0.2 | $1.25 | Cheapest OpenAI model — fine for straightforward tasks. |
| `haiku` | Claude 4.5 Haiku | Anthropic | $1.0 | $5.0 | Cheapest Anthropic model — fine for straightforward tasks. |
| `premium` | Inherit from parent | any | — | — | Runs on the same model as the orchestrator — escape hatch when an implementation step needs full reasoning power. |

## Full catalog

| Model | Provider | Input | Cache write | Cache read | Output | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Claude 4 Sonnet | Anthropic | $3.0 | $3.75 | $0.3 | $15.0 | Hidden by default; Thinking variant counts as 2 requests in legacy pricing |
| Claude 4 Sonnet 1M | Anthropic | $6.0 | $7.5 | $0.6 | $22.5 | Hidden by default; Thinking variant counts as 2 requests in legacy pricing; This model can be very expensive due to the large context window; The cost is 2x when the input exceeds 200k tokens |
| Claude 4.5 Haiku | Anthropic | $1.0 | $1.25 | $0.1 | $5.0 | Hidden by default; Bedrock/Vertex: regional endpoints +10% surcharge; Cache: writes 1.25x, reads 0.1x |
| Claude 4.5 Opus | Anthropic | $5.0 | $6.25 | $0.5 | $25.0 | Hidden by default; Requires Max Mode on request-based plans |
| Claude 4.5 Sonnet | Anthropic | $3.0 | $3.75 | $0.3 | $15.0 | Hidden by default; Requires Max Mode on request-based plans; The cost is 2x when the input exceeds 200k tokens |
| Claude 4.6 Opus | Anthropic | $5.0 | $6.25 | $0.5 | $25.0 | Hidden by default; Requires Max Mode on request-based plans; Up to 1M tokens in Max Mode at the same per-token rates (no long-context surcharge) |
| Claude 4.6 Opus (Fast mode) | Anthropic | $30.0 | $37.5 | $3.0 | $150.0 | Hidden by default; Requires Max Mode on request-based plans; Limited research preview; Up to 1M tokens in Max Mode at the same per-token rates as shorter context |
| Claude 4.6 Sonnet | Anthropic | $3.0 | $3.75 | $0.3 | $15.0 | Requires Max Mode on request-based plans; The cost is 2x when the input exceeds 200k tokens |
| Claude 4.7 Opus | Anthropic | $5.0 | $6.25 | $0.5 | $25.0 | Requires Max Mode on request-based plans; Up to 1M tokens in Max Mode at the same per-token rates (no long-context surcharge) |
| Composer 1 | Cursor | $1.25 | — | $0.125 | $10.0 | Hidden by default |
| Composer 1.5 | Cursor | $3.5 | — | $0.35 | $17.5 | Hidden by default |
| Composer 2 | Cursor | $0.5 | — | $0.2 | $2.5 | - |
| Gemini 2.5 Flash | Google | $0.3 | — | $0.03 | $2.5 | Hidden by default |
| Gemini 3 Flash | Google | $0.5 | — | $0.05 | $3.0 | Hidden by default |
| Gemini 3 Pro | Google | $2.0 | — | $0.2 | $12.0 | Hidden by default |
| Gemini 3 Pro Image Preview | Google | $2.0 | — | $0.2 | $12.0 | Hidden by default; Native image generation model optimized for speed, flexibility, and contextual understanding; Text input and output priced the same as Gemini 3 Pro; Image output: $120/1M tokens (\~$0.134 per 1K/2K image, \~$0.24 per 4K image); Preview models may change before becoming stable and have more restrictive rate limits |
| Gemini 3.1 Pro | Google | $2.0 | — | $0.2 | $12.0 | - |
| GPT-5 | OpenAI | $1.25 | — | $0.125 | $10.0 | Hidden by default; Agentic and reasoning capabilities; Available reasoning effort variant is gpt-5-high |
| GPT-5 Fast | OpenAI | $2.5 | — | $0.25 | $20.0 | Hidden by default; Faster speed but 2x price; Available reasoning effort variants are gpt-5-high-fast, gpt-5-low-fast |
| GPT-5 Mini | OpenAI | $0.25 | — | $0.025 | $2.0 | Hidden by default |
| GPT-5-Codex | OpenAI | $1.25 | — | $0.125 | $10.0 | Hidden by default; Agentic and reasoning capabilities |
| GPT-5.1 Codex | OpenAI | $1.25 | — | $0.125 | $10.0 | Hidden by default; Agentic and reasoning capabilities |
| GPT-5.1 Codex Max | OpenAI | $1.25 | — | $0.125 | $10.0 | Hidden by default |
| GPT-5.1 Codex Mini | OpenAI | $0.25 | — | $0.025 | $2.0 | Hidden by default; Agentic and reasoning capabilities; 4x rate limits compared to GPT-5.1 Codex |
| GPT-5.2 | OpenAI | $1.75 | — | $0.175 | $14.0 | Hidden by default; Agentic and reasoning capabilities; Available reasoning effort variant is gpt-5.2-high |
| GPT-5.2 Codex | OpenAI | $1.75 | — | $0.175 | $14.0 | Hidden by default; Agentic and reasoning capabilities |
| GPT-5.3 Codex | OpenAI | $1.75 | — | $0.175 | $14.0 | Requires Max Mode on request-based plans; Agentic and reasoning capabilities; Available reasoning effort variant is gpt-5.3-codex-high |
| GPT-5.4 | OpenAI | $2.5 | — | $0.25 | $15.0 | Requires Max Mode on request-based plans; Agentic and reasoning capabilities; 90% discount on cached input tokens; Fast mode is 15% faster with 2x pricing; Long context (Max Mode) supports up to 1M tokens with 2x input pricing |
| GPT-5.4 Mini | OpenAI | $0.75 | — | $0.075 | $4.5 | Hidden by default; Smaller, faster variant of GPT-5.4; 90% discount on cached input tokens |
| GPT-5.4 Nano | OpenAI | $0.2 | — | $0.02 | $1.25 | Hidden by default; Smallest GPT-5.4 variant, optimized for cost; 90% discount on cached input tokens |
| Grok 4.20 | xAI | $2.0 | — | $0.2 | $6.0 | The cost is 2x when the input exceeds 200k tokens |
| Kimi K2.5 | Moonshot | $0.6 | — | $0.1 | $3.0 | Hidden by default |
