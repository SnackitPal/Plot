# PLOT: The Cultural Atlas
> **Where the world diverges—and where human consensus quietly holds.**

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-orange?style=for-the-badge)](https://snackitpal.github.io/Plot/)
[![Tests](https://img.shields.io/badge/Tests-110_Passing-emerald?style=for-the-badge)](tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Offline--First_PWA-blue?style=for-the-badge)](preview/)
[![License](https://img.shields.io/badge/License-MIT-gray?style=for-the-badge)](LICENSE)

PLOT is a tactile, deliberative cartography platform designed to map human moral, social, and cultural disagreements across **19 macro-regions** and **15 global city centroids**.

Rather than flattening global opinions into binary poll numbers or algorithmic outrage, PLOT tracks the geographic and epistemic boundaries of human consensus through daily moral slates, empirical benchmarks, and 5D cultural friction modeling.

---

## Key Capabilities

### 1. The Curved Cartogram World Map
- Interactive, tactile SVG cartogram projecting 19 macro-regions with real-time consensus distributions.
- **Floating Map Reticle HUD:** Neobrutalist tooltip tracking cursor movement across borders with live telemetry (dominant choice, regional sample size $n$, flag, and margin).
- **Dual-State Epistemic Switch:** Toggle between **Live Community** responses and **Real-World Empirical Benchmarks** (Pew Research American Trends Panel & World Values Survey Wave 7).
- **Divergence Lens:** Highlights regional fissures where cultural disagreement is widest.

### 2. Instant Inline Consensus & Micro-Tactility
- **Frictionless Deliberation:** Instant choice latching with animated percentage fill bars (`0.16, 1, 0.3, 1` cubic-bezier easing) and count-up readouts directly inside the choice cards.
- **Dual-Transient Mechanical Synthesizer:** Real-time Web Audio API sound engine generating physical keypress snaps (1248Hz) and bottom-out resonance (192Hz) with zero external assets.
- **Post-Vote Absorption Buffer:** Smooth 750ms pacing letting citizens absorb consensus before map exploration.

### 3. 5D Cultural Friction Engine & Relocation Radar
- Computes dimensional delta vectors across 5 core sociological axes:
  - **Autonomy vs. Collectivism**
  - **Punctuality & Chronemics**
  - **Relational Perimeter & Boundary**
  - **Institutional Trust vs. Self-Reliance**
  - **Capital Sovereignty vs. Social Security**
- **Normalized Cultural Shock Index (CSI 0-100%):**
  $$\text{CSI} = \sqrt{\frac{1}{5}\sum_{k=1}^5 \Delta_k^2} \times 100\%$$
- **Survival Protocols:** Actionable behavioral rules, local maxims, and transit codes for 15 global hubs (Tokyo, Zurich, São Paulo, Singapore, London, etc.).
- **Personalized Cultural DNA Dossier:** Comprehensive behavioral readings across Career, Friendship, and Conflict arenas.

### 4. Viral Cultural DNA Battlecards
- Client-side Canvas renderer producing publication-grade editorial share graphics in two formats:
  - **Instagram & TikTok Stories (9:16):** `1080 x 1920 px`
  - **X, Reddit & Messaging Cards (16:9):** `1200 x 675 px`
- Side-by-side **Global Divergence Rift** box comparing user's home region with global counterweights.
- 1-tap **Mobile Web Share API** (`navigator.share`) and desktop clipboard image copying.

### 5. 30-Day Daily Slates & Atlas Archive
- Curated corpus of **150 non-obvious moral dilemmas** across 7 thematic domains.
- Full-text search and category chip discovery engine with 300ms debouncing.
- 5-question daily streak milestone ritual modal.

---

## Architecture & Technology Stack

- **Frontend:** Single-file tactile HTML5 PWA with Tailwind CSS, SVG Cartography, Web Audio API, and HTML5 Canvas.
- **PWA & Offline Resilience:** Service Worker cache with IndexedDB `OfflineActionQueue` ensuring 100% offline availability and background synchronization.
- **Backend:** Python REST API with SQLite relational storage (`atlas/storage/schema.sql`).
- **Statistical Pipeline:** Empirical Bayes shrinkage estimator for low-sample stabilization, Thompson sampling multi-armed bandit, and harmonic cohort bridging.
- **Testing:** 110 automated tests (`pytest`) covering API contracts, algorithmic correctness, and PWA offline fallbacks.

---

## Quickstart

### Prerequisites
- Python 3.10+
- Modern web browser (Chrome, Safari, Firefox, Edge)

### Installation
```bash
# Clone the repository
git clone https://github.com/SnackitPal/Plot.git
cd Plot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Launch Preview Server
```bash
python serve_preview.py --port 8000
```
Visit `http://localhost:8000/` in your browser.

### Run Automated Tests
```bash
pytest -v
```

---

## Live Static Demo

Experience the interactive prototype on GitHub Pages:
**[https://snackitpal.github.io/Plot/](https://snackitpal.github.io/Plot/)**

---

## License

MIT License. Developed as a public deliberative cartography project.
