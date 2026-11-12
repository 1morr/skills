<!-- project-init 的範本：取代 docs/agents/issue-tracker.md〈Conventions〉底下的清單，其餘段落不動。 -->
- One milestone per directory: `.scratch/<milestone>/` (`m0`, `m1`, …); an effort that is not a milestone (a docs cleanup, an audit) uses `.scratch/<effort-slug>/` with the same layout
- The spec is `.scratch/<milestone>/spec.md`, with the sections 目標, 範圍, 共同規則, 驗收, 票序. It is written as the first step of the fresh session where the user runs `/to-tickets docs/plan.md 拆 <milestone> 的票`, before the tickets are drafted, by refining the milestone's section in `docs/plan.md`; that section then shrinks to one line linking here. Milestones not yet opened have no `.scratch/` directory and live only in the plan
- Implementation issues are one file per ticket at `.scratch/<milestone>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file; a ticket inserted later takes the previous number plus a letter (`14b`)
- Each ticket names what to read (`讀: plan §x、brief §y`) and lists its acceptance criteria as checkboxes under `## 驗收`
- The last ticket of a milestone is the acceptance ticket `<NN>-<milestone>-acceptance.md`, blocked by every other ticket
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings); a finished ticket is `Status: done`
- Blocking is a `Blocked by:` line under `Status:`, listing ticket numbers or `None`
- Comments and conversation history append to the bottom of the file under a `## Comments` heading
