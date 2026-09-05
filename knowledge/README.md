# Knowledge

This directory is the digital twin's memory of Adam. Every file here is
loaded, whole, into the twin's system prompt, so **anything written here is
public**: a visitor can get the twin to repeat it. Sensitive material is
kept out entirely, never hidden.

## Conventions

Every `.md` file except this one and anything under `raw/` starts with YAML
frontmatter:

```yaml
---
title: Recorded Future
kind: role            # identity | voice | boundaries | arc | role | topic | project | faq
period: 2018-07 to 2022-08   # roles and projects only; ends are YYYY or YYYY-MM, or "present"
tags: [cti, product-architecture]
public: true          # required; the loader refuses to start without it
reviewed: 2026-09-10  # set by Adam when he has read and approved the file
---
```

Loading order: identity, voice, boundaries, arc, roles newest first, topics,
projects, faq. Within a kind, files sort by filename.

Role files use these headings, in this order, and leave a heading empty
rather than guessing: Context, What I did, Outcomes, Stories, Skills used,
Why I moved on.

`raw/` is gitignored. It holds the verbatim sources: the resume text, the
LinkedIn profile export, Adam's short summary, and the monologue transcript;
interview notes join them as the interviews happen. `topics/` holds opinion
pieces as the monologue and interviews produce them.

## Workflow

1. Adam delivers his practiced career monologue in chat. It is saved
   verbatim to `raw/YYYY-MM-DD-monologue.md`.
2. Claude drafts or revises files from the sources. Nothing is invented.
3. Interviews go role by role, newest first, with six prompts each: why you
   joined and what the company does; the work; outcomes and numbers; two or
   three stories; what you learned; why you moved on. Answers are appended
   verbatim to `raw/interviews/<role-slug>.md` and folded into the role file.
4. Adam reads each file when he is satisfied and sets `reviewed`. Files
   without a `reviewed` date are never pushed.
5. **After every session, copy `raw/` to a OneDrive folder.** It is the only
   copy of the source material and git does not track it.

## Coverage

| File | Seeded | Interviewed | Reviewed |
|---|---|---|---|
| `identity.md` | resume + LinkedIn (About, headline, location) + summary + spec, pass 1; monologue, pass 2 | | |
| `voice.md` | monologue, pass 2 | | |
| `boundaries.md` | defaults, pass 1 | | |
| `career-arc.md` | monologue, pass 2 | | |
| `roles/2026-corelight.md` | resume + LinkedIn end date, pass 1; monologue, pass 2 | 2026-09-05, first round; outcomes and stories still thin | |
| `roles/2023-accenture.md` | resume, pass 1; monologue, pass 2 | 2026-09-05, first round; numbers still thin | |
| `roles/2022-pondurance-revelstoke.md` | one narrative from the 2026-09-05 interview, nothing beyond it by Adam's choice | 2026-09-05, final | |
| `roles/2018-recorded-future.md` | resume + LinkedIn, pass 1; monologue, pass 2 | 2026-09-05, first round | |
| `roles/2017-mit-lincoln-lab.md` | resume, pass 1; monologue, pass 2 | 2026-09-05, closed by Adam's choice | |
| `roles/2017-mission-essential.md` | resume, pass 1; monologue, pass 2 | 2026-09-05, mission added, then closed | |
| `roles/2013-mang-training-manager.md` | resume, pass 1; monologue, pass 2 | 2026-09-05, closed by Adam's choice | |
| `roles/2001-army-intel-ops.md` | resume, pass 1; monologue, pass 2 | 2026-09-05, regions added, then closed | |
| `topics/cti-advisory.md` | monologue + LinkedIn, pass 2 | | |
| `topics/ai-in-secops.md` | Corelight interview, 2026-09-05 | | |
| `topics/first-principles-for-customer-work.md` | Recorded Future interview, 2026-09-05 | | |
| `projects/digital-twin.md` | spec, pass 1 | | |
| `faq.md` | resume + LinkedIn + summary + spec, pass 1; monologue, pass 2 | | |
