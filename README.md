# Stateless MCP Server on Azure App Service

A reference implementation of a **stateless, horizontally scaled MCP server**,
deployed behind Azure App Service's built-in load balancer.

* **Stateless HTTP transport** (MCP `2025-11-25`) — any instance can serve any request
* **Three App Service instances** by default, no sticky sessions
* **Staging deployment slot** for zero-downtime updates
* **Application Insights** auto-instrumentation with per-instance request tagging
* **k6 load test** that visualizes load distribution

## What's in the box

```
.
├── main.py                       # FastAPI app exposing MCP over stateless HTTP
├── requirements.txt
├── azure.yaml                    # azd service definition
├── infra/
│   ├── main.bicep                # Resource group scope
│   ├── main.parameters.json
│   ├── abbreviations.json
│   ├── app/
│   │   └── web.bicep             # App Service + staging slot
│   └── shared/
│       ├── app-service-plan.bicep
│       └── monitoring.bicep      # Log Analytics + App Insights
├── loadtest/
│   ├── k6-mcp.js                 # k6 script — tags hits per instance
│   └── README.md
├── static/style.css
└── templates/index.html          # Status page showing serving instance
```

## MCP tools

| Tool             | Purpose                                                                  |
| ---------------- | ------------------------------------------------------------------------ |
| `whoami`         | Returns the App Service instance ID handling the request                 |
| `echo`           | Echoes a message, tagged with the instance ID                            |
| `lookup_fact`    | Static read-only fact lookup (stateless)                                 |
| `compute_primes` | CPU-bound prime counter (useful for load testing each instance's CPU)    |

## Local development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Open <http://localhost:8000/>.

The MCP endpoint is at `http://localhost:8000/mcp`. A `.vscode/mcp.json` is
included so VS Code can connect to it as a local MCP server.

## Deploy to Azure

```bash
azd auth login
azd up
```

`azd up` provisions:

* A Premium v3 (P0v3) Linux App Service Plan with **`capacity: 3`** — that's
  three live instances behind App Service's built-in load balancer.
* The Web App, with **`clientAffinityEnabled: false`** — no ARR Affinity
  cookie, so the load balancer is free to round-robin every request.
* A `staging` deployment slot wired to the same plan for zero-downtime swaps.
* A Log Analytics workspace + Application Insights resource, connected via
  `APPLICATIONINSIGHTS_CONNECTION_STRING` so the OpenTelemetry distro emits
  traces tagged with `cloud_RoleInstance = WEBSITE_INSTANCE_ID`.

### Tune the scale-out level

```bash
azd env set INSTANCE_COUNT 5
azd provision
```

(The `instanceCount` bicep parameter accepts 1–10.)

### Connect VS Code to the deployed server

Update `.vscode/mcp.json`:

```json
{
  "servers": {
    "stateless-mcp-app-service": {
      "url": "https://<your-app>.azurewebsites.net/mcp",
      "type": "http"
    }
  }
}
```

## Verify load distribution

1. Hit the home page a few times — the **Instance ID** value should change.
2. Run the k6 load test:

   ```bash
   BASE_URL=https://<your-app>.azurewebsites.net k6 run loadtest/k6-mcp.js
   ```

3. Inspect Application Insights:

   ```kusto
   requests
   | where timestamp > ago(15m)
   | where name contains "/mcp"
   | summarize count() by cloud_RoleInstance
   ```

## Architecture

```
                       ┌─────────────────────────────────────────┐
                       │       Azure App Service (P0v3 × 3)      │
                       │  ┌────────────┐ ┌────────────┐ ┌──────┐ │
   MCP client ── HTTP ─┤ ▶  instance0  │ │  instance1 │ │  …   │ │
   (stateless,         │  └────────────┘ └────────────┘ └──────┘ │
    no cookies)        │     ▲ built-in load balancer ▲          │
                       │     │   clientAffinityEnabled=false     │
                       │  ┌──┴────────────────────────────────┐  │
                       │  │       Staging slot (same plan)    │  │
                       │  └───────────────────────────────────┘  │
                       └────────────────────┬────────────────────┘
                                            ▼
                                   Application Insights
                                  (cloud_RoleInstance =
                                   WEBSITE_INSTANCE_ID)
```

## License

MIT.
