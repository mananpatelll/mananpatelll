<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/hero-light.svg">
  <img alt="Manan Patel — AI Engineer working on agentic LLM systems, multi-agent orchestration, retrieval and RAG, and LLM evaluation. Builds agentic LLM systems and the evals that catch them being confidently wrong, currently pointed at markets. M.S. Computer Science, Temple University. Philadelphia, PA. 4 publications and abstracts. Open to AI engineering roles." src="assets/hero-light.svg" width="100%">
</picture>

<a href="mailto:manan305@icloud.com">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/link-email-dark.svg">
    <img alt="Email manan305@icloud.com" src="assets/link-email-light.svg" height="42">
  </picture>
</a>
<a href="https://www.linkedin.com/in/manan305">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/link-linkedin-dark.svg">
    <img alt="LinkedIn: manan305" src="assets/link-linkedin-light.svg" height="42">
  </picture>
</a>
<a href="https://github.com/mananpatelll?tab=repositories">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/link-github-dark.svg">
    <img alt="GitHub repositories" src="assets/link-github-light.svg" height="42">
  </picture>
</a>

</div>

---

### `$ whoami`

AI engineer in Philadelphia, mostly building agentic LLM systems.

Day to day that means LangGraph and multi-agent orchestration, retrieval and RAG,
and the evals that keep both honest — with Python, PyTorch and vector databases
underneath. Full stack further down.

Before that: a year of clinical ML research at Temple, and a summer on an equity
research desk.

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/projects-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/projects-light.svg">
  <img alt="Current project: Multi-Agent Trading Desk, in progress. A deterministic scanner screens the S&P 500, three specialist agents review what it finds, and a pure-code risk gate gets the last word — including the option to say no. Built with LangGraph, human-in-the-loop review, a risk gate and a trade journal. The chart is a schematic of the system, not a measured result." src="assets/projects-light.svg" width="100%">
</picture>
</div>

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/pipeline-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/pipeline-light.svg">
  <img alt="Architecture diagram of the trading desk: a deterministic scanner screens the S&P 500, routes candidates to three parallel LLM agents (technical, news, events), a trader agent synthesizes them, and a pure-code risk gate either produces a proposal for human approval and the trade journal, or returns NO-TRADE." src="assets/pipeline-light.svg" width="100%">
</picture>
</div>

The trading desk in diagram form. Three things I'd keep if I started it over:

- **The model doesn't get the last word.** Sizing, stops, R:R floors — plain code
  the LLM can't talk its way around.
- **Don't make an LLM do a for-loop.** Screening 500 tickers is a rules problem.
  Agents only where judgment actually helps.
- **`NO-TRADE` is a real answer.** Something that can't say no isn't managing risk.

---

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/timeline-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/timeline-light.svg">
  <img alt="Career timeline plotted as a course between four waypoints. Stage 1, 2023: Technical Analyst at Arihant Investments — screened equities for breakout setups, wrote daily trade reports. Stage 2, 2024–25: ML Research Assistant at Temple University — clinical AI on linked EHR data, NIH-funded (U01, NIDCR). Stage 3, 2025: Research Lead at Civic Interactions Lab — led an undergrad capstone team as their lead and stakeholder. Stage 4, 2025 onward, the current leg: Independent AI Engineer, self-directed — agentic systems, retrieval, and the evals that keep them honest. Education: M.S. Computer Science, Temple University 2024–25; B.C.A., Charotar University 2020–23." src="assets/timeline-light.svg" width="100%">
</picture>
</div>

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/stack-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/stack-light.svg">
  <img alt="Technical stack. LLM and agentic: LangChain, LangGraph, LangSmith, Anthropic, OpenAI, Pydantic, Ollama; multi-agent orchestration, corrective RAG, MCP servers, human-in-the-loop, LLM-as-judge, structured outputs, prompt engineering, local inference. Machine learning: PyTorch, Transformers, scikit-learn, XGBoost, NumPy, SciPy, MLflow; embeddings, fine-tuning, feature engineering, hyperparameter search, cross-validation, ablation studies. Data and infrastructure: Python, SQL, pandas, FastAPI, Docker, Kubernetes, AWS, CUDA, Qdrant, Git; vector databases, reproducible pipelines, seeded deterministic runs, cost and latency instrumentation. Markets: equities and options, technical analysis, position sizing, reward-to-risk floors, stop placement, trade journaling. Clinical AI: clinical NLP, ICD-10 and CDT coding, linked EHR-EDR records, feature reduction, clinician-in-the-loop validation." src="assets/stack-light.svg" width="100%">
</picture>
</div>

### `$ ls publications/`

From the Temple research year — I wrote code on these, not prose.

- **AI-Driven Application for Feature Reduction in Linked EHR** — abstract, 2025
  AADOCR/CADR Annual Meeting, New York, NY. <sub>*Co-author*</sub>
- **Developing Deep Learning Models to Improve Dental Radiograph Clarity and
  Quality** — abstract, 2025 IADR/PER General Session, Barcelona, Spain.
  <sub>*Co-author*</sub>
- **Periodontitis prediction model with linked electronic health records** —
  *JDR Clinical & Translational Research*, 2025. <sub>*Programming contributor*</sub>
- **Orthodontic NLP model for automated clinical note information extraction** —
  *Orthodontics & Craniofacial Research*, 2024.
  [`10.1111/ocr.12944`](https://doi.org/10.1111/ocr.12944)
  <sub>*Programming contributor*</sub>

---

<div align="center">

**Open to AI engineering roles** — agentic systems, LLM evaluation, applied ML.
Happy to talk about any of it.

<sub>Every graphic here is a hand-rolled SVG built by
<a href="assets/src/build.py"><code>assets/src/build.py</code></a> — no badge
services, no external fonts, no runtime requests, no JavaScript. Motion is SMIL
and CSS keyframes, which is all that runs inside GitHub's image sandbox.</sub>

</div>
