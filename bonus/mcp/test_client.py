"""test_client.py — connect to the MCP server and exercise its tool."""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # Launch the server as a subprocess, talk to it over stdio
    server_params = StdioServerParameters(
        command="python",
        args=["bgp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover what the server offers
            tools_response = await session.list_tools()
            print("Tools advertised by the server:")
            for tool in tools_response.tools:
                first_line = tool.description.splitlines()[0]
                print(f"  - {tool.name}: {first_line}")
            print()

            # Call the tool
            for node in ("r1", "r2", "r3"):
                result = await session.call_tool(
                    "get_bgp_state",
                    arguments={"node": node},
                )
                print(f"=== {node} ===")
                print(result.content[0].text)
                print()


if __name__ == "__main__":
    asyncio.run(main())
