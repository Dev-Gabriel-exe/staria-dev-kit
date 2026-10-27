---
name: frontend-performance
description: Use when a web app has poor load speed, interaction latency, oversized bundles, hydration costs, or mobile performance problems.
---

# Performance de frontend

1. Reproduce and measure baseline (network, device, build mode, request waterfall).
2. Prioritize bottlenecks: unnecessary JS, large assets, re-renders, fonts, WebGL and blocking resources.
3. Use code splitting, image sizing, memoization only when justified, caching with invalidation.
4. Do not optimize without an observed issue or reliable profile.
5. Compare pre/post measurements on representative hardware and note trade-offs.
