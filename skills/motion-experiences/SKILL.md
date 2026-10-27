---
name: motion-experiences
description: Use when a frontend needs animation, transitions, scroll storytelling, microinteractions, GSAP, Motion, or Anime.js.
---

# Animações e microinterações

1. Decide what animation communicates; write down a reduced-motion alternative first.
2. Inspect the frontend catalog for Motion.dev, GSAP/ScrollTrigger, Anime.js and interaction references.
3. Prefer CSS for simple hover/state transitions, Motion for React layout/gesture work, GSAP for choreographed timelines.
4. Avoid main-thread animation loops when transform and opacity suffice.
5. Test keyboard navigation, touch, reduced-motion and mid-range Android performance.
6. Validate that pinned scroll and smooth scrolling do not trap the user.
