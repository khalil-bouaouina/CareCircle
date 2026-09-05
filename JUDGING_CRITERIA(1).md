# MuslimHacks Judging Criteria — Reference for AI Agents

> This file documents how this project will be judged at MuslimHacks. AI agents assisting with this project (planning, coding, writing docs, preparing the pitch, etc.) should treat these criteria as priority context when making decisions, and should proactively flag gaps against them.

## Scoring Overview

| Category | Weight | Focus |
|---|---|---|
| `business_level` | 40% | Problem-fit, usability, sustainability, research justification |
| `delivery` | 30% | Live demo quality, presentation clarity, pitch strength, Q&A handling |
| `technical_level` | 30% | Architecture, code quality, testing, or (for non-software projects) research depth and use cases |

Each criterion is scored 1–5:
`1 = Poor, 2 = Needs improvement, 3 = Satisfying, 4 = Good, 5 = Impressive`

**Weighting implication for agents:** `business_level` has the highest weight. When trading off effort between polishing code internals vs. clarifying the problem statement/justification/user story, default to prioritizing the business narrative unless the technical gap is severe enough to break the demo.

---

## 1. Business Level (40%) — applies to all projects

| Criterion | What is evaluated |
|---|---|
| Problem-solving | Does the project clearly solve the target problem or a well-defined aspect of it? |
| Ease of use | Is it understandable and usable without extensive explanation? |
| Cost sustainability | Is the "cost of running" this solution sustainable (hosting, APIs, maintenance)? |
| Justification / research | Is the choice of problem convincing? Was there real research behind it? |

**Agent action items:**
- When drafting README/pitch content, always state the problem explicitly, why it matters, and what research or data backs the choice.
- When designing the architecture, flag any dependency with non-trivial recurring cost (paid APIs, GPU inference, etc.) and, if possible, note a cheaper/sustainable fallback.
- Optimize UX copy and onboarding flow for first-time clarity — assume the "user" is a judge who has 2–3 minutes.

---

## 2. Delivery (30%) — applies to all projects

| Criterion | What is evaluated |
|---|---|
| Live demo | Does it actually work live? |
| Clarity of presentation | Is the project clearly presented and described? |
| Pitch strength | Is the pitch convincing enough that judges would "invest"? |
| Q&A handling | How well does the team answer follow-up questions (see Section 4)? |

**Agent action items:**
- Prioritize demo stability over feature count. A smaller feature set that runs reliably live outperforms a larger one prone to failure.
- Generate/maintain a scripted demo path (a fixed sequence of actions/inputs known to work) as a fallback, separate from free-form exploration.
- Help draft a pitch structure: problem → solution → live demo → impact/business case.
- Pre-generate concise, honest answers to the Section 4 questions and keep them versioned alongside the project.

---

## 3. Technical Level (30%)

Criteria branch by project type.

### 3A. Software Product

| Criterion | What is evaluated |
|---|---|
| Architecture | Is the dominant architecture discernible and appropriate for the project? |
| Code quality | Cohesion, coupling, understandability |
| Performance | How does the system perform? |
| Testing | Is it well-tested? What is the test coverage? |
| Process clarity | Can the team clearly describe how they arrived at this solution? |

**Agent action items:**
- Keep the architecture legible: consistent module boundaries, a short ARCHITECTURE.md or diagram, no unexplained magic.
- Maintain at least minimal automated tests for core logic; report coverage if feasible — absence of any tests is explicitly penalized.
- Avoid premature/unnecessary complexity that obscures "dominant architecture" — judges are explicitly checking if it's discernible.
- Log/document key technical decisions and tradeoffs as they're made, so the team (or an agent) can reconstruct "the process" on demand.

### 3B. Non-Software Project (model, system, study, etc.)

| Criterion | What is evaluated |
|---|---|
| Solution comprehensiveness | Is the proposed model/system comprehensive? |
| Research support | Was the solution supported by market/community research? |
| Use cases | Are there well-thought-out use cases? |
| Process clarity | Can the team clearly describe how they arrived at this solution? |

**Agent action items:**
- Ensure deliverables include explicit, concrete use cases (not just abstract descriptions).
- Cite or summarize the research/data that supports feasibility and demand.
- Document the reasoning trail behind the proposed model/system.

---

## 4. Standard Follow-Up Questions (prepare answers in advance)

Judges ask a default question set plus improvised ones. Agents helping prep the team should draft short, honest, consistent answers for each bucket below and keep them in a shared doc (e.g., `docs/qa_prep.md`).

**Technical Implementation**
1. What is the delivery format — mobile, web, CLI?
2. What technologies, APIs, or frameworks did you use?
3. How does your system work behind the scenes?
4. Did you build this from scratch during the hackathon?
5. What technical tradeoffs did you make due to time constraints?

**Impact and Users**
1. Who is your target user, and how would they use this?
2. How would users discover or adopt this solution?
3. How many people could realistically benefit from this?
4. What kind of impact could this have if fully developed?
5. How would you measure whether this project is successful?

**Demo & Functionality**
1. Is the demo fully functional, or are some parts mocked/prototyped?
2. What is the most important feature you completed?
3. What was the hardest part of building this?
4. What did you actually complete versus prototype or mock?

**Business & Scalability**
1. What is your potential business model?
2. How would this scale beyond the hackathon prototype?
3. What would it take to turn this into a real product?
4. Who would pay for your app?

**Team & Process**
1. How did the team divide the work?
2. What did you learn during the hackathon?
3. What would you do differently next time?
4. How did you decide which features to prioritize?

**Data & Privacy**
1. What data does your project use?
2. How do you handle privacy or security concerns?
3. Are there any ethical risks with your solution?
4. Does your solution depend on an LLM?

**Future Plans**
1. What would you build next if you had more time?
2. Do you plan to continue working on this?
3. What would be your first step after today?

**Closing Questions**
1. What makes your solution different from existing options?
2. What help or resources would you need to keep going?
3. What do you want the judges/audience to remember most?
4. Why should this project win?

---

## Priority Checklist for Agents

Before considering the project "submission-ready," verify:

- [ ] Problem statement + supporting research are explicit and documented (business_level)
- [ ] Running-cost/sustainability of the solution is addressed or mitigated (business_level)
- [ ] A stable, scripted demo path exists and has been tested end-to-end (delivery)
- [ ] Pitch narrative (problem → solution → demo → impact) is drafted (delivery)
- [ ] Answers to Section 4 questions are drafted and reviewed by the team (delivery)
- [ ] Architecture is documented and its "dominant pattern" is identifiable (technical_level — software)
- [ ] Minimal automated tests exist for core logic (technical_level — software)
- [ ] Use cases and market/community research are documented (technical_level — non-software)
