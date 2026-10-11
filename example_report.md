# Q3 2026 Engineering Report

*Platform team quarterly summary*  
**Author:** Michal Stojke  
**Date:** 2026-08-26  

## Executive Summary

The platform team shipped **14 features** this quarter while reducing infrastructure spend by **18%**. Details below; raw dashboards are available [here](https://example.com/dashboards).

> Best quarter for platform reliability since 2024.

## Key Metrics

| Metric | Q2 | Q3 | Change |
| :--- | ---: | ---: | ---: |
| Uptime | 99.92% | 99.98% | +0.06 pp |
| p95 latency | 410 ms | 290 ms | -29% |
| Monthly cost | $48k | $39k | -18% |

*Quarter-over-quarter platform metrics*

## Highlights

- **New deploy pipeline** — rollouts now take 4 minutes
- Migrated the job queue to `redis-streams`
  - Zero-downtime cutover
  - Old queue decommissioned
- *Docs overhaul* for internal APIs

### Deploy pipeline

The new pipeline is configured with a single manifest:

```yaml
pipeline:
  stages: [build, test, canary, rollout]
  canary_traffic: "5%"
```

---

*Generated with the *`reportsmith`* library.*
