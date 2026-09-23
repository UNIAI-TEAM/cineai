# CineAI cinematic homepage implementation plan

**Goal:** Rebuild the homepage around the supplied Vietnamese CineAI reference, using newly generated cinematic imagery before implementation.

**Architecture:** Keep the existing React router, authentication destinations, shared brand mark and language selector. Scope the dark marketing design to the homepage. Build real HTML controls and responsive layouts; generated mockups are references, never flattened page backgrounds containing text.

**Tech stack:** React 19, TypeScript, plain CSS, lucide-react, existing Vite and browser test tooling. No new application dependencies.

## Visual specification

- Reference: `/Users/ducquang/Downloads/2026-09-23 13.32.06.jpg`.
- Near-black green canvas, lime primary actions, white headings, muted light body copy. Slim navigation, split cinematic hero, two product cards, creation tools, image gallery, Studio workflow, character continuity, inspiration, pricing entry points, closing CTA and footer.
- Desktop content approximately 1200px wide, 48–80px between major sections; tablet grids wrap and mobile layouts stack without horizontal page overflow.
- User explicitly requested CLI image generation. Generate hero and section design references plus clean, text-free media using the bundled imagegen CLI. Store originals and prompts in `output/imagegen/homepage`; optimized runtime images in `frontend/public/homepage`.
- Preserve English/Vietnamese switching. Use actual product destinations. Do not present unverified statistics, customer quotes, model availability, or monthly prices as live facts; preserve those areas' visual role with supported product information and links to current pricing.

## Execution

- [x] Generate and inspect section references and standalone media before writing homepage implementation.
- [x] Record baseline browser rendering and existing authentication destinations.
- [x] Replace `frontend/src/pages/HomePage.tsx`; add focused homepage components/content and scoped `frontend/src/styles/homepage.css`.
- [x] Connect Create to existing tools and Studio to `/drama`; ensure guest redirects preserve the intended destination. Any prompt composer must preserve its prompt through authentication into the chosen tool.
- [x] Keep pricing tied to the existing `/pricing` surface and do not introduce billing behavior.
- [x] Run `npm run lint`, `npm test`, and `npm run build` in `frontend`.
- [x] Browser-check Vietnamese and English, desktop and phone widths, all images, category filters, mobile navigation, CTAs, prompt handoff, and keyboard access.
- [x] Capture screenshots; compare to the user's reference and generated section references with `visual-verdict`; persist verdict and remaining image/style differences under `.omx/state/homepage-redesign/ralph-progress.json`.

## Completion evidence

Final report must include changed source/assets, checks performed, preview artifact locations, and any remaining fidelity or runtime limitations. Keep existing unrelated workspace changes intact.

## Verification result

- Frontend production build passed; existing large-bundle and mixed-import warnings remain.
- Frontend unit tests: 57 passed, 0 failed.
- Lint: exit 0, 0 errors; 37 warnings across the existing frontend.
- Browser assertions passed at 320, 390, 768, 1024, 1280 and 1440px widths. No horizontal overflow, clipped controls, broken images, or page errors.
- Vietnamese/English switching, mobile menu and Escape focus return, category filtering, prompt starters, guest Studio redirect, draft persistence across a simulated auth boundary, StrictMode restoration and one-time draft consumption passed.
- Live billing catalogue and pricing API failure fallback both verified. No paid media generation was triggered through the application.
- Visual verdict: 92/100, pass; see `.omx/state/homepage-redesign/ralph-progress.json`.
- Independent code review: no remaining critical/high/medium findings; final control-label nit addressed.
- Final previews: `output/imagegen/homepage/previews/`.
