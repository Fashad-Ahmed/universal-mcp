# Example MCP Client Configs

Drop-in configs for connecting `universal-db-mcp` to common MCP clients.
Copy the relevant block into your client's MCP config file and adjust the
environment variables for your database.

| File | Client | Config location |
|------|--------|------------------|
| `claude_desktop_config.json` | Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| `cursor_mcp.json` | Cursor | `.cursor/mcp.json` (project) or global settings |
| `windsurf_mcp_config.json` | Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| `docker_mcp_config.json` | Any client, via Docker | runs the server in a container instead of `uvx` |

For Claude Code, see the main [README](../README.md#zero-setup-works-on-your-laptop-right-now)
for the `~/.claude/mcp_servers.json` setup.
