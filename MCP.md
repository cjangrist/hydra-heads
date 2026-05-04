# Remote HTTP MCP Server Configuration — Per-CLI Reference

Reference for configuring each AI coding CLI in `hydra_heads/providers/` to connect to a **remote HTTP-streamable MCP server**.

Example server URL used throughout: `https://your-mcp-server.example.com/mcp` (publicly accessible — no `Authorization` header required).

---

## Summary Table

| CLI | Remote HTTP MCP | Config path | Verified? |
|---|---|---|---|
| claude | ✅ native (`type: "http"`) | `~/.claude.json` (user) or `.mcp.json` (project) | ✅ official docs |
| codex | ✅ native (`url` field in TOML) | `~/.codex/config.toml` | ✅ official docs + PR #4317 |
| gemini | ✅ native (`httpUrl` field) | `~/.gemini/settings.json` | ✅ official docs + PR #13762 |
| qwen | ✅ native (`httpUrl` — gemini-cli fork) | `~/.qwen/settings.json` | ✅ official docs |
| kilo | ✅ native (`type: "remote"`) | `~/.config/kilo/kilo.json` | ✅ official docs (CLI add has bug #7079) |
| kimi | ✅ native | `~/.kimi/mcp.json` | ✅ official docs |
| opencode | ✅ native (`type: "remote"`, auto SH→SSE fallback) | `opencode.json[c]` or `~/.config/opencode/opencode.json` | ✅ source code (PR #444 + e8eaa77) |
| factory | ✅ native (`type: "http"`) | `~/.factory/mcp.json` | ✅ official docs |
| goose | ✅ native (`type: streamable_http`) | `~/.config/goose/config.yaml` | ✅ official docs + issue #6576 |
| pi | ⚠️ via extension only (`pi-mcp-adapter`) | `~/.pi/agent/mcp.json` (after install) | ✅ via npm package + author blog |
| ob1 | ❓ undocumented publicly | unverified — likely `~/.ob1/settings.json` | ⚠️ schema NOT on openblocklabs.com |
| aider | ❌ no MCP support | N/A | ✅ confirmed: issue #4506 still open |

---

## claude (Anthropic Claude Code CLI)

**Remote-HTTP MCP support:** Yes — first-class `--transport http` (Streamable HTTP).

**Config file:** `~/.claude.json` (local/user scope, written by `claude mcp add`); `.mcp.json` at project root (project scope, committable). User-scope HTTP entries land in `~/.claude.json`.

**JSON snippet** (project scope `.mcp.json` or local-scope nested under `projects.<path>.mcpServers`):

```json
{
  "mcpServers": {
    "omnisearch": {
      "type": "http",
      "url": "https://your-mcp-server.example.com/mcp"
    }
  }
}
```

**CLI add command:**

```bash
claude mcp add --transport http omnisearch https://your-mcp-server.example.com/mcp
```

Add `--scope user` or `--scope project` to change scope. `--header "Authorization: Bearer …"` for auth headers.

**Auth/headers:** None required for a public server. Optional `--header` flag adds `Authorization`/custom headers; the keys land under a `headers` object in the JSON entry.

**Sources:**
- https://code.claude.com/docs/en/mcp — Anthropic Claude Code MCP docs
- https://thepromptshelf.dev/blog/claude-code-mcp-setup-guide/ — Claude Code MCP setup guide 2026
- https://systemprompt.io/guides/claude-code-mcp-servers-extensions — independent guide

---

## codex (OpenAI Codex CLI)

**Remote-HTTP MCP support:** Yes — Streamable HTTP, added via PR #4317 (https://github.com/openai/codex/pull/4317). Both CLI and TOML support it.

**Config file:** `~/.codex/config.toml` (global) or `.codex/config.toml` (project, trusted only).

**TOML snippet:**

```toml
[mcp_servers.omnisearch]
url = "https://your-mcp-server.example.com/mcp"
# optional:
# bearer_token_env_var = "OMNISEARCH_TOKEN"
# http_headers = { "X-Custom" = "value" }
# env_http_headers = { "Authorization" = "OMNISEARCH_TOKEN" }
# startup_timeout_sec = 10
# tool_timeout_sec = 60
```

Presence of `url` selects Streamable HTTP transport; `command` is mutually exclusive (would select stdio). There is no `transport = "..."` literal key — it is inferred. Some community blog posts mention `transport = "streamable_http"` but the official `config-reference` page lists only `url` / `bearer_token_env_var` / `http_headers` / `env_http_headers`.

**CLI add command:**

```bash
codex mcp add omnisearch --url https://your-mcp-server.example.com/mcp
# with auth:
# codex mcp add omnisearch --url <url> --bearer-token-env-var OMNISEARCH_TOKEN
```

`--url` is mutually exclusive with the positional stdio command.

**Auth/headers:** Public server needs none. For auth, prefer `bearer_token_env_var` (sources from env) over `bearer_token` (plaintext). OAuth login is supported only for Streamable HTTP servers.

**Sources:**
- https://developers.openai.com/codex/mcp — official MCP docs
- https://developers.openai.com/codex/config-reference — config reference
- https://github.com/openai/codex/pull/4317 — PR adding Streamable HTTP support

---

## gemini (Google Gemini CLI)

**Remote-HTTP MCP support:** Yes — Streamable HTTP via `httpUrl` key (or `url` + `type: "http"` after PR #13762 consolidation, with auto-fallback HTTP→SSE).

**Config file:** `~/.gemini/settings.json` (user) or `.gemini/settings.json` (project).

**JSON snippet (canonical `httpUrl` form):**

```json
{
  "mcpServers": {
    "omnisearch": {
      "httpUrl": "https://your-mcp-server.example.com/mcp",
      "timeout": 5000,
      "trust": false
    }
  }
}
```

`httpUrl` selects Streamable HTTP; `url` selects SSE (legacy). Optional `headers`, `includeTools`, `excludeTools`.

**CLI add command:**

```bash
gemini mcp add --transport http omnisearch https://your-mcp-server.example.com/mcp
# with header:
# gemini mcp add --transport http omnisearch <url> -H "Authorization: Bearer …"
```

**Auth/headers:** None required for a public server. OAuth 2.0 supported for remote servers; `headers` object or `-H` flag for static headers.

**Sources:**
- https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md — official MCP docs (GitHub main)
- https://geminicli.com/docs/tools/mcp-server/ — mirrored docs
- https://github.com/google-gemini/gemini-cli/pull/13762 — PR consolidating remote MCP to use `url`

---

## qwen (Qwen Code)

**Remote-HTTP MCP support:** Yes, native. Supports stdio, SSE, and Streamable HTTP. Transport auto-inferred from which key is set: `httpUrl` → Streamable HTTP, `url` → SSE, `command` → stdio. Precedence: `httpUrl > url > command`.

**Config file:** `~/.qwen/settings.json` (user) or `.qwen/settings.json` (project).

**JSON snippet** (under top-level `mcpServers` object):

```json
{
  "mcpServers": {
    "omnisearch": {
      "httpUrl": "https://your-mcp-server.example.com/mcp",
      "timeout": 30000,
      "trust": false
    }
  }
}
```

Optional fields per the schema: `headers`, `description`, `includeTools`, `excludeTools`.

**CLI add command:**

```bash
qwen mcp add --transport http omnisearch https://your-mcp-server.example.com/mcp
```

Add `-s user` for user scope; `-H "K: V"` for headers; `--timeout`, `--trust`, `--include-tools`, `--exclude-tools` available.

**Auth/headers:** None needed for public servers. Omit `headers`.

**Sources:**
- https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/ — settings reference
- https://qwenlm.github.io/qwen-code-docs/en/developers/tools/mcp-server/ — MCP-server developer docs
- https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/settings.md — source

---

## kilo (KiloCode CLI — `@kilocode/cli`)

**Remote-HTTP MCP support:** Yes — Streamable HTTP is the default for remote servers; SSE deprecated. The CLI tries Streamable HTTP first, falls back to SSE.

**Config file:** `~/.config/kilo/kilo.json` (or `.jsonc`) global; `./kilo.json` / `./.kilo/kilo.json` project.

**Caveat:** Known bug (kilocode #7079, CLI 7.0.47) makes `kilo mcp add` write to `opencode.jsonc` instead — manual edit of `kilo.json` is the workaround.

**JSON snippet (CLI canonical form — `type: "remote"`):**

```json
{
  "mcp": {
    "omnisearch": {
      "type": "remote",
      "url": "https://your-mcp-server.example.com/mcp",
      "enabled": true
    }
  }
}
```

Optional: `headers` object, `timeout` (default 5000ms).

**Disagreement between surfaces:** the **CLI docs** use `type: "remote"`; the VS Code extension surface and some Kilo docs reference `type: "streamable-http"` (kebab-case). For `@kilocode/cli` specifically, official CLI docs say `"remote"`.

**Runtime auto-append:** On first read after a manual write, the kilo runtime will append a `permission` block at the top level if absent — e.g.:

```json
{
  "$schema": "https://kilo.ai/config.json",
  "mcp": {
    "omnisearch": {
      "type": "remote",
      "url": "https://your-mcp-server.example.com/mcp",
      "enabled": true
    }
  },
  "permission": {
    "bash": "allow"
  }
}
```

This is **CLI-level** auto-approval policy (governs all tool calls — built-in *and* MCP-routed) and is **separate** from per-MCP-server auth. Don't confuse it with `mcp.<name>.headers` / `mcp.<name>.oauth`, which are server-specific.

**CLI add command:**

```bash
kilo mcp add        # interactive; no documented non-interactive flags
kilo mcp list
kilo mcp auth omnisearch    # for OAuth-enabled servers
```

The CLI reference lists no `--url` / `--transport` flags for `kilo mcp add`; manual JSON edit is the reliable path.

**Auth/headers:** None required for a public server. Optional `headers` object (e.g., `Authorization`); supports `{env:VAR_NAME}` interpolation; OAuth 2.0 auto-flow when server advertises it (disable with `"oauth": false`).

**Permissions vs. MCP server auth — quick orientation:**

| Concept | Where it lives | Scope |
|---|---|---|
| Tool auto-approval policy | `permission.<tool>: "allow"\|"ask"\|"deny"` (top-level) or `KILO_PERMISSION` env var | CLI-wide; applies to bash/edit/write/MCP tool calls uniformly |
| MCP server connection auth | `mcp.<name>.headers` / `.oauth` / `.bearerToken` | Per-server only |

**Sources:**
- https://kilo.ai/docs/automate/mcp/using-in-cli — official MCP-in-CLI docs
- https://kilo.ai/docs/automate/mcp/using-in-kilo-code — VS Code extension surface
- https://kilo.ai/docs/code-with-ai/platforms/cli-reference — CLI command reference
- https://github.com/Kilo-Org/kilocode/issues/3316 — naming-mismatch issue

---

## kimi (MoonshotAI Kimi CLI)

**Remote-HTTP MCP support:** Yes (HTTP and SSE transports, alongside stdio).

**Config file:** `~/.kimi/mcp.json`

**JSON snippet:**

```json
{
  "mcpServers": {
    "omnisearch": {
      "url": "https://your-mcp-server.example.com/mcp"
    }
  }
}
```

Optional `"headers": {}` block; omit for public servers.

**CLI add command:**

```bash
kimi mcp add --transport http omnisearch https://your-mcp-server.example.com/mcp
```

**Auth/headers:** None required for a public server. If headers are needed, kimi expects `KEY: VALUE` form (space after colon) via `--header`.

**Sources:**
- https://moonshotai.github.io/kimi-cli/en/customization/mcp.html — official MCP docs
- https://moonshotai.github.io/kimi-cli/en/reference/kimi-mcp.html — `kimi mcp` subcommand reference
- https://github.com/MoonshotAI/kimi-cli — repo

---

## opencode (sst/opencode)

**Remote-HTTP MCP support:** Yes. As of `sst/opencode` PR #444 (merged 2025-06-27) and follow-up commit `e8eaa77` in the active fork `anomalyco/opencode`, `type: "remote"` now attempts `StreamableHTTPClientTransport` first and falls back to SSE automatically. A separate `type: "http"` is also accepted.

**Config file:** `opencode.json` or `opencode.jsonc` in project root, or `~/.config/opencode/opencode.json` for global.

**JSON snippet:**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "omnisearch": {
      "type": "remote",
      "url": "https://your-mcp-server.example.com/mcp",
      "enabled": true
    }
  }
}
```

Optional keys: `headers`, `oauth: {}`, `timeout: 5000`.

**CLI add command alternative:** None — opencode is config-file-driven. Run `/mcp` inside the TUI to verify the server connects.

**Auth/headers:** None for public servers. If needed, add `"headers": { "Authorization": "Bearer ..." }`.

**Sources:**
- https://opencode.ai/docs/mcp-servers/ — official MCP-servers docs
- https://opencode.ai/docs/config/ — config reference
- https://github.com/sst/opencode/pull/444 — PR adding HTTP Streaming transport
- https://github.com/anomalyco/opencode/commit/e8eaa77bf1714af985f82faf2cee6950ec3ea0f3 — StreamableHTTP+SSE auto-fallback commit

---

## factory (Factory Droid CLI — `droid`)

**Remote-HTTP MCP support:** Yes, native. Two transports supported: `http` (remote) and `stdio` (local). Factory uses the type identifier `"http"` — note this differs from clients that use `"streamable-http"`.

**Config file:** `~/.factory/mcp.json` (user) or `.factory/mcp.json` (project). User config takes precedence when both define the same server.

**JSON snippet:**

```json
{
  "mcpServers": {
    "omnisearch": {
      "type": "http",
      "url": "https://your-mcp-server.example.com/mcp",
      "disabled": false
    }
  }
}
```

Optional fields: `headers` (object), `disabledTools` (string array).

**CLI add command:**

```bash
droid mcp add omnisearch https://your-mcp-server.example.com/mcp --type http
# with auth header (repeatable):
# droid mcp add omnisearch <url> --type http --header "Authorization: Bearer …"
```

Servers added via CLI always land in `~/.factory/mcp.json`. Verify with `droid mcp` or the in-TUI `/mcp` panel.

**Auth/headers:** None needed for public servers. Omit `headers`.

**Sources:**
- https://docs.factory.ai/cli/configuration/mcp — official MCP config docs
- https://docs.factory.ai/reference/cli-reference — CLI command reference

---

## goose (Block Goose)

**Remote-HTTP MCP support:** Yes — explicit `streamable_http` extension type.

**Config file:** `~/.config/goose/config.yaml` (macOS/Linux) or `%APPDATA%\Block\goose\config\config.yaml` (Windows).

**YAML snippet:**

```yaml
extensions:
  omnisearch:
    enabled: true
    type: streamable_http
    name: omnisearch
    uri: https://your-mcp-server.example.com/mcp
    timeout: 300
```

Optional `headers:` map for auth, e.g. `Authorization: "Bearer ..."`.

**Important:** Goose uses `uri:` (not `url:`) for streamable_http extensions in config.yaml; the deeplink format and some recipes use `url=` as the query param. The recipe-reference docs show the same shape inside a `recipe.yaml`.

**CLI add command alternatives:**

```bash
# Interactive
goose configure   # → "Add Extension" → "Remote Extension (Streamable HTTP)" → paste URL

# Session-only
goose session --with-streamable-http-extension "https://your-mcp-server.example.com/mcp"

# Deeplink
goose://extension?url=https://your-mcp-server.example.com/mcp&type=streamable_http&id=omnisearch&name=omnisearch
```

**Auth/headers:** None for public servers. Headers are supported under the `headers:` map.

**Sources:**
- https://block.github.io/goose/docs/guides/config-file/ — configuration file docs
- https://block.github.io/goose/docs/guides/recipes/recipe-reference/ — recipe reference (extensions schema)
- https://deepwiki.com/block/goose/5.4-custom-mcp-server-integration — custom MCP server integration
- https://github.com/block/goose/issues/6576 — confirms `streamable_http` / `uri` / `headers` keys

---

## pi (Pi Coding Agent — `@mariozechner/pi-coding-agent`)

**Remote-HTTP MCP support:** Not native. Mario Zechner deliberately omitted MCP from the core agent (he considers the per-tool token overhead excessive). Remote HTTP MCP is supported via the **community extension `pi-mcp-adapter`** (proxies all MCP tools through one ~200-token proxy tool). The adapter supports stdio, Streamable HTTP (with SSE fallback), and SSE.

**Install adapter first:**

```bash
npm install -g @mariozechner/pi-coding-agent
pi install npm:pi-mcp-adapter
```

**Config file** (precedence — later overrides earlier):

1. `~/.config/mcp/mcp.json` (user-global shared, cross-host)
2. `~/.pi/agent/mcp.json` (Pi global override)
3. `.mcp.json` (project-local shared)
4. `.pi/mcp.json` (Pi project override)

**JSON snippet** (use `url` to indicate HTTP transport — adapter auto-detects Streamable HTTP / SSE):

```json
{
  "mcpServers": {
    "omnisearch": {
      "url": "https://your-mcp-server.example.com/mcp",
      "lifecycle": "lazy",
      "idleTimeout": 10
    }
  }
}
```

Optional fields: `headers` (supports `${VAR}` interpolation), `auth` (`"bearer"` | `"oauth"`), `bearerToken` / `bearerTokenEnv`, `directTools`, `exposeResources`, `toolPrefix`.

**CLI add command alternative:** None for adding individual servers — config is JSON-edited. Verify with `/mcp` panel inside a pi session; reconnect via `/mcp reconnect <name>`.

**Auth/headers:** None needed for public servers. Omit `headers`.

**Sources:**
- https://github.com/nicobailon/pi-mcp-adapter — adapter repo
- https://www.npmjs.com/package/pi-mcp-adapter — npm package
- https://www.npmjs.com/package/@mariozechner/pi-coding-agent — pi npm
- https://mariozechner.at/posts/2025-11-30-pi-coding-agent/ — author's design notes (explains MCP omission)

---

## ob1 (OpenBlock Labs OB-1)

**Remote-HTTP MCP support:** Unclear from official docs. The public Owner's Manual at `openblocklabs.com/manual` lists "Configuration" and "MCP Servers" only as section headings with no published schema. A third-party-grounded answer reports `~/.ob1/settings.json` with `mcpServers.<id>.transport: "streamableHttp"` and `url`, but this is **not directly verifiable from openblocklabs.com**. Official docs only confirm "MCP-compatible tool" support generally.

**Config file location (UNVERIFIED):** `~/.ob1/settings.json`

**JSON snippet (UNVERIFIED — confirm with team@openblocklabs.com or `/migrate` from a known-good Claude Code config):**

```json
{
  "mcpServers": {
    "omnisearch": {
      "transport": "streamableHttp",
      "url": "https://your-mcp-server.example.com/mcp"
    }
  }
}
```

**CLI add command alternative:** Not documented publicly. The `/migrate` slash-command imports Claude Code config — that is the documented onboarding path.

**Auth/headers:** Not documented. Server is public, so none expected.

**Recommendation:** Confirm exact schema via Discord (`discord.gg/5ZwShCSxzz`) or by running `ob1` and inspecting `~/.ob1/` after adding via UI/slash command — do not blindly trust the third-party schema.

**Sources:**
- https://www.openblocklabs.com/manual — Owner's Manual (confirms MCP sections exist; content not exposed)
- https://grokipedia.com/page/OB-1_OpenBlock_Labs — install command, generic MCP support
- https://www.openblocklabs.com/enterprise — "MCP-based custom integrations"

---

## aider (Aider — `aider-chat`)

**Remote-HTTP MCP support:** None. No MCP support at all. Not stdio, not HTTP. Verified via aider's `HISTORY.html` (no MCP entries through 0.86.x and main) and the still-open feature request issue #4506 ("Add native MCP server and Agent Mode support") which has no maintainer-shipped implementation.

Aider's context tools remain `/web`, `/run`, `/read-only`. Third-party wrappers like `disler/aider-mcp-server` expose Aider *as* an MCP server to other clients; they do not let aider consume a remote MCP server.

**Config file:** N/A. Aider's config (`.aider.conf.yml`, env vars, CLI flags) has no MCP fields.

**Sources:**
- https://github.com/Aider-AI/aider/issues/4506 — open feature request "Add native MCP server and Agent Mode support"
- https://aider.chat/HISTORY.html — release history (no MCP through 0.86.x)
- https://aider.chat/docs/config.html — config reference (no MCP fields)

---

## Notable Schema Differences (NON-UNIFORM!)

The `type` key value varies wildly across CLIs — there is no single common form:

| Variant | Used by |
|---|---|
| `"http"` | claude, factory |
| `"remote"` | kilo, opencode |
| `"streamable_http"` (snake) | goose |
| `"streamableHttp"` (camel, unverified) | ob1 |
| no `type` (transport inferred from `url` presence) | codex |
| no `type` (transport inferred from `httpUrl` vs `url`) | gemini, qwen |

**URL key also varies:**

| Variant | Used by |
|---|---|
| `url` | claude, codex, kilo, kimi, opencode, factory, ob1, pi |
| `httpUrl` | gemini, qwen |
| `uri` | goose (YAML) |

**Config format:**

- **JSON:** claude, gemini, qwen, kilo, kimi, opencode, factory, pi, ob1
- **TOML:** codex
- **YAML:** goose

**Auth-by-env preference:**

- Codex uses `bearer_token_env_var` (sources from env, avoids plaintext) over `bearer_token`.
- Pi adapter supports `${VAR}` interpolation in `headers`.
- Most others accept literal `headers.Authorization`.

---

## Verification Status

- **9 verified from official docs/source:** claude, codex, gemini, qwen, kilo, kimi, opencode, factory, goose
- **2 require care:**
  - **pi** — needs `pi-mcp-adapter` extension installed first; verified via npm + author blog
  - **ob1** — schema NOT published on openblocklabs.com; confirm via `/migrate` flow or Discord
- **1 dead-end:** **aider** — no MCP support; tracked in open issue #4506 with no maintainer commitment
