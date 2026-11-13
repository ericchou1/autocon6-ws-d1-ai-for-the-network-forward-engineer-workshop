# Bonus: MCP — Model Context Protocol

**Time:** ~15 min
**Prerequisites:** Lab 3 completed.

In Lab 3, the BGP tool was a Python function decorated with `@tool` — running in the same process as the agent. That's convenient, but it couples the tool tightly to the agent code. **MCP standardizes tools as separate processes** that any MCP-compatible client can talk to: your LangChain agent, Claude Desktop, Cursor, custom UIs, anything that speaks the protocol.

The capability doesn't change. The boundary does — and that boundary unlocks composability across the ecosystem.

## Concept

```
Lab 3 — tightly coupled              MCP — protocol-mediated
─────────────────────────            ─────────────────────────

┌──────────────────────┐             ┌──────────┐    ┌────────┐
│  agent.py            │             │  agent   │◄──►│  MCP   │
│  ┌────────────────┐  │             │ (client) │    │ server │
│  │ @tool def      │  │             └──────────┘    │  (BGP) │
│  │ get_bgp_state  │  │                  ▲          └────────┘
│  └────────────────┘  │                  │              ▲
└──────────────────────┘                  │              │
                                     ┌────┴─────┐        │
                                     │ Claude   │────────┘
                                     │ Desktop  │   (any client
                                     └──────────┘    can connect)
```

One MCP server can serve many clients. One client can use many servers. The boundary is the protocol, not the import path.

## Step 1: Install the SDK and write the server

```bash
pip install "mcp>=2"
```

See `bgp_server.py` in this folder. (If you've seen older MCP examples: the server class was called `FastMCP` in the 1.x SDK and is `MCPServer` in 2.x — same decorator, same `run()`.)

Two things to notice:

- **`@mcp.tool()` looks identical to LangChain's `@tool`.** The decorator pattern is the same; what's different is what happens underneath. `MCPServer` registers the function with the MCP protocol layer, not the agent layer.
- **No agent code, no LLM client in this file.** The server is *just the tool*. The LLM (and its reasoning loop) lives on the client side. This is the architectural shift: separation of concerns enforced by a process boundary.

> **Why no Pydantic parser here?** Lab 3's `get_bgp_state` did two things — fetch data *and* run Lab 2's LLM-powered parser. In the MCP world, the server's job is just data access. The client (the LLM doing the reasoning) interprets whatever the server returns. Mixing LLM calls into your MCP server is possible but architecturally muddier.

## Step 2: Verify the server works

See `test_client.py` in this folder.

Run it:

```bash
cd bonus/mcp
python test_client.py
```

**Expected:** the client launches `bgp_server.py` as a subprocess, discovers its tools, then calls `get_bgp_state` three times. You'll see the raw BGP output for r1, r2, and r3 — the same captures Lab 3's tool reads, now flowing through the MCP protocol.

Note what just happened: the server and client are separate processes, communicating through stdin/stdout using the MCP JSON-RPC protocol. The same server could be talking to Claude Desktop, a Cursor extension, or your LangChain agent. You wrote the tool once; it's now reusable across the entire MCP ecosystem.

## Going Further

### 1. Use the MCP server from a LangChain agent

The `langchain-mcp-adapters` package bridges MCP servers into LangChain. Install it and wire the agent from Lab 3 to use the MCP server instead of the in-process `@tool`:

```bash
pip install langchain-mcp-adapters
```

The adapter turns the server's tools into LangChain tools, so in Lab 3's `agent.py` you'd replace `tools=[get_bgp_state]` in `build_agent()` with the adapter's list. `create_agent`, `ask()`, the Streamlit app and the tracing all stay identical; only where the tool lives changes. This is the moment the "boundary unlocks composability" claim becomes concrete.

### 2. Configure Claude Desktop to use the server

Claude Desktop (Anthropic's macOS/Windows app) has built-in MCP support. Adding the BGP server is a config-file edit:

```json
{
  "mcpServers": {
    "network-tools": {
      "command": "python",
      "args": ["/absolute/path/to/bonus/mcp/bgp_server.py"]
    }
  }
}
```

Restart Claude Desktop. Now you can chat with Claude directly about your network topology — it will discover `get_bgp_state` automatically and call it when relevant. Same server, different client, zero code changes on either side.

### 3. Add more tools

Extend `bgp_server.py` with additional `@mcp.tool()` functions: `get_ospf_state`, `get_route_table`, `diagnose_session`. Each one becomes available to every client connected to the server. This is how an MCP server grows from "one capability" to "a useful tool surface."

### 4. HTTP transport instead of stdio

`mcp.run()` defaults to stdio (process-piped JSON-RPC). For network-accessible servers, MCP also supports HTTP/SSE transports. Look at `mcp.server.streamable_http` for the HTTP variant. That's how you'd build a centrally-hosted MCP server that serves your whole NetOps team rather than running locally for one developer.
