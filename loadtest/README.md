# Load test

A k6 script that exercises the MCP server over its stateless HTTP transport
and tags each response with the App Service instance that served it.

## Install k6

Full docs: <https://grafana.com/docs/k6/latest/set-up/install-k6/>

### macOS

```bash
brew install k6
```

### Windows

```powershell
# winget (recommended)
winget install k6 --source winget

# or Chocolatey
choco install k6
```

### Linux (Debian / Ubuntu)

```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### Docker (any OS)

```bash
docker run --rm -i -e BASE_URL=https://<your-app>.azurewebsites.net \
  -v "$PWD":/scripts grafana/k6 run /scripts/k6-mcp.js
```

## Run against your deployed App Service

macOS / Linux:

```bash
BASE_URL=https://<your-app>.azurewebsites.net k6 run loadtest/k6-mcp.js
```

Windows PowerShell:

```powershell
$env:BASE_URL = "https://<your-app>.azurewebsites.net"
k6 run loadtest/k6-mcp.js
```

Windows cmd:

```cmd
set BASE_URL=https://<your-app>.azurewebsites.net
k6 run loadtest\k6-mcp.js
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
