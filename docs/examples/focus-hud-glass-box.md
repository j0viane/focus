## Focus

Traced `auth_utils.py`. **CRITICAL** risk — 4 downstream files, up to 2 hops away. Danger Zones: `api/routes.py`.

### Architecture impact

Legend: each box is a **file**; an arrow means **change flows to** (that file imports / depends on the previous one).

```mermaid
flowchart LR
  %% Nodes = files. Arrow = change flows to (is used by).
  subgraph api [Api]
    n_api_routes_py["api/routes.py"]
  end
  subgraph billing [Billing]
    n_billing_service_py["billing/service.py"]
  end
  subgraph dashboard [Dashboard]
    n_dashboard_views_py["dashboard/views.py"]
  end
  subgraph jobs [Jobs]
    n_jobs_worker_py["jobs/worker.py"]
  end
  subgraph root [Root]
    n_auth_utils_py["auth_utils.py ⭐"]
  end
  n_auth_utils_py --> n_billing_service_py
  n_auth_utils_py --> n_dashboard_views_py
  n_auth_utils_py --> n_jobs_worker_py
  n_billing_service_py --> n_api_routes_py
```

### Blast radius

🔴 **Danger Zones** *(risky if wrong — shared or API/schema/config)*
- `api/routes.py` — This is an API route file — 2 import steps away from a file you changed.

🟡 **Also affected** *(these files depend on what you changed)*
- `billing/service.py` — Directly imports `auth_utils.py`.
- `dashboard/views.py` — Directly imports `auth_utils.py`.
- `jobs/worker.py` — Directly imports `auth_utils.py`.

🟢 **Not pulled in** *(no dependents found for this change)*
- (none for this change)

**Caveat:** Static analysis only. Runtime imports, dynamic dispatch, and cross-repo dependencies may not appear in this graph.
