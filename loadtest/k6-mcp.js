// k6 load test for the Stateless MCP Server on App Service.
//
// What it does:
//   • Drives concurrent MCP `tools/call` requests against /mcp
//   • Alternates between `whoami` (cheap) and `compute_primes` (CPU-bound)
//   • Tallies which App Service instance handled each response, so you can
//     see horizontal load distribution from k6 itself — no portal required.
//
// Run:
//   BASE_URL=https://<your-app>.azurewebsites.net k6 run loadtest/k6-mcp.js
//
// Or against the staging slot:
//   BASE_URL=https://<your-app>-staging.azurewebsites.net k6 run loadtest/k6-mcp.js
//
// Install k6: https://grafana.com/docs/k6/latest/set-up/install-k6/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const PRIME_LIMIT = Number(__ENV.PRIME_LIMIT || 20000);

const instanceHits = new Counter('mcp_instance_hits');
const toolLatency = new Trend('mcp_tool_latency_ms', true);

export const options = {
  scenarios: {
    steady_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: 10 },
        { duration: '45s', target: 30 },
        { duration: '30s', target: 30 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{tool:whoami}': ['p(95)<800'],
  },
};

function callTool(name, args, tags) {
  const payload = JSON.stringify({
    jsonrpc: '2.0',
    id: `${name}-${__VU}-${__ITER}`,
    method: 'tools/call',
    params: { name, arguments: args },
  });

  const res = http.post(`${BASE_URL}/mcp`, payload, {
    headers: { 'Content-Type': 'application/json' },
    tags: Object.assign({ tool: name }, tags || {}),
  });

  check(res, {
    'status 200': (r) => r.status === 200,
    'no jsonrpc error': (r) => {
      try {
        return !JSON.parse(r.body).error;
      } catch (_) {
        return false;
      }
    },
  });

  toolLatency.add(res.timings.duration, { tool: name });

  try {
    const body = JSON.parse(res.body);
    const text = body.result && body.result.content && body.result.content[0] && body.result.content[0].text;
    if (text) {
      const inner = JSON.parse(text);
      const instance = inner.instance_id || 'unknown';
      instanceHits.add(1, { instance });
    }
  } catch (_) {
    // ignore parse errors — the check above will already fail
  }

  return res;
}

export function setup() {
  const res = http.post(
    `${BASE_URL}/mcp`,
    JSON.stringify({ jsonrpc: '2.0', id: 'init', method: 'initialize' }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'initialize 200': (r) => r.status === 200 });
}

export default function () {
  // 80% cheap whoami pings, 20% CPU-heavy compute_primes.
  // The mix is intentional: whoami stress-tests the load balancer's even
  // distribution; compute_primes stress-tests each instance's CPU.
  if (Math.random() < 0.8) {
    callTool('whoami', {});
  } else {
    callTool('compute_primes', { limit: PRIME_LIMIT });
  }
  sleep(0.2 + Math.random() * 0.4);
}

export function handleSummary(data) {
  const lines = ['', '=== Instance distribution ==='];
  const counters = data.metrics.mcp_instance_hits;
  if (counters && counters.values && counters.values.count) {
    lines.push(`Total tagged calls: ${counters.values.count}`);
  }
  lines.push(
    'Inspect the per-instance breakdown with --summary-export or by reading',
    'http_reqs / mcp_instance_hits tagged by `instance` in your k6 output.',
    '',
  );
  return {
    stdout: lines.join('\n') + JSON.stringify(data.metrics.mcp_instance_hits || {}, null, 2),
  };
}
