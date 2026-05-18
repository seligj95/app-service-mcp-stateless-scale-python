# Load test

A k6 script that exercises the MCP server over its stateless HTTP transport
and tags each response with the App Service instance that served it.

## Install k6

<https://grafana.com/docs/k6/latest/set-up/install-k6/>

```bash
# macOS
brew install k6
```

## Run against your deployed App Service

```bash
BASE_URL=https://<your-app>.azurewebsites.net k6 run loadtest/k6-mcp.js
```

## Run against the staging slot

```bash
BASE_URL=https://<your-app>-staging.azurewebsites.net k6 run loadtest/k6-mcp.js
```

## Run locally

```bash
BASE_URL=http://localhost:8000 k6 run loadtest/k6-mcp.js
```

## What to look for

* `http_req_failed` should stay below 1%.
* `http_req_duration{tool:whoami}` p95 should be well under a second.
* The custom `mcp_instance_hits` counter is tagged with `instance` —
  exporting the summary will show how requests are distributed across
  App Service instances:

  ```bash
  k6 run --summary-export=summary.json loadtest/k6-mcp.js
  jq '.metrics.mcp_instance_hits.values' summary.json
  ```

  You should see roughly even hit counts across each `instance` tag —
  proof that App Service's load balancer is round-robining requests with
  no sticky session involvement.

## Cross-check in Application Insights

In the Azure portal, open Application Insights → **Logs** and run:

```kusto
requests
| where timestamp > ago(15m)
| where name contains "/mcp"
| summarize count() by cloud_RoleInstance
| order by count_ desc
```

`cloud_RoleInstance` is populated from `WEBSITE_INSTANCE_ID` automatically.
