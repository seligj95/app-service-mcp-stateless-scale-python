"""
Stateless MCP Server on Azure App Service
A FastAPI application that exposes MCP tools over stateless HTTP transport.
Designed to run behind App Service's built-in load balancer with N instances —
no sticky sessions, no in-process state.
"""

import json
import os
import socket
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Optional: Azure Monitor OpenTelemetry distro auto-instruments FastAPI and
# enriches every request span with cloud_RoleInstance (= WEBSITE_INSTANCE_ID),
# so request distribution across instances is visible in Application Insights.
try:
    from azure.monitor.opentelemetry import configure_azure_monitor

    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        configure_azure_monitor(
            logger_name="mcp",
            disable_offline_storage=False,
        )
        _APP_INSIGHTS_ENABLED = True
    else:
        _APP_INSIGHTS_ENABLED = False
except Exception:
    _APP_INSIGHTS_ENABLED = False


# ---------- Static facts (read-only, in-process) ----------
# Stateless lookups: identical inputs return identical outputs on every
# instance. No writes, no shared cache, no session affinity required.
FACTS: Dict[str, str] = {
    "app-service": (
        "Azure App Service is a fully managed PaaS for hosting web apps and APIs. "
        "It includes built-in load balancing across instances when you scale out."
    ),
    "mcp": (
        "The Model Context Protocol (MCP) is an open standard for exposing tools, "
        "resources, and prompts to LLM clients. The 2025-06-18 revision supports "
        "stateless HTTP transport for horizontally scaled deployments."
    ),
    "stateless-http": (
        "Stateless HTTP transport lets each MCP request stand on its own — any "
        "instance can handle any request, which is the prerequisite for load "
        "balancing without sticky sessions."
    ),
    "deployment-slots": (
        "App Service deployment slots are live staging environments you can warm "
        "up and then swap into production with zero downtime."
    ),
}


# ---------- MCP tool implementations ----------
async def tool_whoami() -> Dict[str, Any]:
    """Return identifiers for the instance handling this request.

    Useful for visually confirming that the load balancer is distributing
    requests across instances.
    """
    return {
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local"),
        "hostname": socket.gethostname(),
        "site_name": os.environ.get("WEBSITE_SITE_NAME", "local"),
        "slot_name": os.environ.get("WEBSITE_SLOT_NAME", "local"),
        "pid": os.getpid(),
        "served_at": time.time(),
    }


async def tool_echo(message: str) -> Dict[str, Any]:
    """Echo a message back along with the serving instance ID."""
    return {
        "message": message,
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local"),
    }


async def tool_lookup_fact(topic: str) -> Dict[str, Any]:
    """Look up a static fact by topic (stateless dictionary read)."""
    key = (topic or "").strip().lower()
    if key in FACTS:
        return {"topic": key, "fact": FACTS[key], "found": True}
    return {
        "topic": key,
        "found": False,
        "available_topics": sorted(FACTS.keys()),
    }


async def tool_compute_primes(limit: int = 5000) -> Dict[str, Any]:
    """CPU-bound: count primes <= limit. Capped to keep one request small.

    Useful for load testing — emit many of these and watch instances spread
    the work in Application Insights.
    """
    limit = max(2, min(int(limit), 50_000))
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, int(limit ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i :: i] = bytearray(len(sieve[i * i :: i]))
    count = int(sum(sieve))
    return {
        "limit": limit,
        "prime_count": count,
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local"),
    }


MCP_TOOLS: Dict[str, Dict[str, Any]] = {
    "whoami": {
        "function": tool_whoami,
        "description": (
            "Return the App Service instance ID and hostname serving this "
            "request. Use it to verify load distribution."
        ),
        "parameters": {},
    },
    "echo": {
        "function": tool_echo,
        "description": "Echo a message back, tagged with the serving instance.",
        "parameters": {
            "message": {"type": "string", "description": "Message to echo"},
        },
    },
    "lookup_fact": {
        "function": tool_lookup_fact,
        "description": "Look up a static fact about App Service, MCP, or scaling.",
        "parameters": {
            "topic": {"type": "string", "description": "Topic to look up"},
        },
    },
    "compute_primes": {
        "function": tool_compute_primes,
        "description": (
            "Count primes <= limit. CPU-bound; useful for load testing."
        ),
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Upper bound, max 50000",
            },
        },
    },
}


# ---------- FastAPI app ----------
app = FastAPI(
    title="Stateless MCP Server on App Service",
    description=(
        "Reference implementation of a horizontally scaled MCP server over "
        "stateless HTTP, deployed on Azure App Service."
    ),
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    host = request.headers.get("host", "localhost:8000")
    proto = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "mcp_url": f"{proto}://{host}/mcp",
            "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local"),
            "site_name": os.environ.get("WEBSITE_SITE_NAME", "local"),
            "slot_name": os.environ.get("WEBSITE_SLOT_NAME", "local"),
            "app_insights_enabled": _APP_INSIGHTS_ENABLED,
            "tools": MCP_TOOLS,
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "stateless-mcp-app-service",
        "protocol_version": "2025-06-18",
        "instance_id": os.environ.get("WEBSITE_INSTANCE_ID", "local"),
        "slot_name": os.environ.get("WEBSITE_SLOT_NAME", "local"),
        "app_insights": _APP_INSIGHTS_ENABLED,
    }


# ---------- MCP transport: stateless JSON-RPC over HTTP ----------
def _server_info() -> Dict[str, Any]:
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": "stateless-mcp-app-service",
            "version": "1.0.0",
        },
    }


@app.get("/mcp")
async def mcp_info():
    return {"jsonrpc": "2.0", "result": _server_info()}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method", "")
    msg_id = body.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": _server_info()}

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": info["parameters"],
                },
            }
            for name, info in MCP_TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if tool_name not in MCP_TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found",
                },
            }

        try:
            result = await MCP_TOOLS[tool_name]["function"](**arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result, indent=2)}
                    ]
                },
            }
        except TypeError as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Invalid params: {e}"},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(e)},
            }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"},
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
