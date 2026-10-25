"""A deterministic MCP service for stdio and Streamable HTTP tests."""

import argparse

from fastmcp import FastMCP

mcp = FastMCP("lab-example")


@mcp.tool
async def add(a: int, b: int) -> int:
    """Add two integers without external effects."""
    return a + b


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="0.0.0.0", port=args.port)
    else:
        mcp.run()
