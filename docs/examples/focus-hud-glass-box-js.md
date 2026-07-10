## Focus

Traced `authUtils.ts`. **CRITICAL** risk — 4 downstream files, up to 2 hops away. Danger Zones: `api/routes.ts`.

### Architecture impact

Legend: each box is a **file**; an arrow means **change flows to** (that file imports / depends on the previous one).

```mermaid
flowchart LR
  %% Nodes = files. Arrow = change flows to (is used by).
  subgraph api [Api]
    n_api_routes_ts["api/routes.ts"]
  end
  subgraph billing [Billing]
    n_billing_service_ts["billing/service.ts"]
  end
  subgraph dashboard [Dashboard]
    n_dashboard_views_ts["dashboard/views.ts"]
  end
  subgraph jobs [Jobs]
    n_jobs_worker_ts["jobs/worker.ts"]
  end
  subgraph root [Root]
    n_authUtils_ts["authUtils.ts ⭐"]
  end
  n_authUtils_ts --> n_billing_service_ts
  n_authUtils_ts --> n_dashboard_views_ts
  n_authUtils_ts --> n_jobs_worker_ts
  n_billing_service_ts --> n_api_routes_ts
```

### Blast radius

🔴 **Danger Zones** *(risky if wrong — shared or API/schema/config)*
- `api/routes.ts` — This is an API route file — 2 import steps away from a file you changed.

🟡 **Also affected** *(these files depend on what you changed)*
- `billing/service.ts` — Directly imports `authUtils.ts`.
- `dashboard/views.ts` — Directly imports `authUtils.ts`.
- `jobs/worker.ts` — Directly imports `authUtils.ts`.

🟢 **Not pulled in** *(no dependents found for this change)*
- (none for this change)

**Caveat:** Static analysis only. Runtime imports, dynamic dispatch, and cross-repo dependencies may not appear in this graph.
