# Handover: who did what

Who built which part of Handover. Outside datasets, models and tools are listed in [sources.md](sources.md). How commit authors are recorded is explained at the [end of this file](#how-commits-are-credited).

## A note on this repository's contribution numbers

GitHub's contribution numbers for this repository (the Contributors page and each person's commit count) do not show who did the work, so please use this file instead. There are two reasons.

**Early commits show "Claude" as the author.** Seven commits from the first day were saved with "Claude" as the author, when the team member should have been the author with Claude as co-author. Three are Theo's: the app setup, the first doctor screen, and the write-up skeleton with the first credits list. Theo did this coding before his git name and email were set up on his computer, so GitHub credits his early app work to Claude, not to him. The other four are Daniel's early data commits (the ignore file, the patient split and its follow-up, and the first five patients' records). One more early commit shows "Daniel" with Claude's email address. We fixed the settings afterwards, but GitHub cannot change who is shown as the author of commits that are already saved.

**Covered tasks count for whoever pushed them.** We worked through two nights, so teammates covered each other's tasks while someone was asleep. A covered task is counted under the person whose computer pushed it, not the person whose task it was.

All three of us wrote our code with Claude Code (Anthropic). Each person below decided what to build, checked the results and is credited for the parts they were responsible for.

## Our team and who was responsible for what

We split the work into three lanes: Abby tested, Daniel built the tool, and Theo built the app. Names are in alphabetical order.

### Abby: testing and scoring

- **Scoring:** the scoring script, which counts missed facts and false alarms separately; the tests for the six merge rules; and scoring the 20 working patients.
- **Baselines and the results table:** the keyword search baseline and the "keyword search plus our merge rules" comparison row. She proposed the step-by-step results table, which shows what each part of the tool adds.
- **Checking the test itself:** an independent check of all 180 answer keys against the original Synthea data, by script and by hand. It found that medicines started before November 2016 were left out of the records, which became one of our stated limits.
- **The main results:** held-out scoring of every method (the step-by-step table, the age and sex breakdown, the planted traps, the cost per patient), and the guards that keep held-out patients out of tuning.
- **Failure analysis:** the three failure examples, and the finding that one cause (a combination medicine written as "X and Y") explains 9 of the 13 misses and 43 of the 47 false alarms.
- **Extra tests:** the omission check, and scoring the 40 trap notes and the 12 MTSamples notes.
- **Write-up and video:** the findings behind the Limitations section, the final write-up and the README, the sources list, this file, and the first version of the video script.
- **Ideas for the app:** the review of the live app that led to the polish, and the ideas for the "Who can confirm this" box and the older-record box.

### Daniel: the tool and the data

- **Setup:** the shared record format, the GitHub repository and its working rules (CLAUDE.md), and the patient split (20 working, 160 held-out).
- **Test data:** the demo patient, the three hospital record templates with planted traps, the answer key script and the brand-name to generic-name table.
- **The AI tool:** the extraction prompt, the Check step, the six merge rules, saving every reply, and choosing Claude Sonnet 5.5 on the 20 working patients.
- **Runs and comparisons:** the freeze, the held-out runs, writing the 40 trap notes, labelling the 12 MTSamples notes, and the medSpaCy and Microsoft Azure comparisons.
- **The app, after Theo's first version:** the records replay, the How we tested tab and its charts, the clinical look, the changes from Abby's review, and live mode for the finals.
- **Write-up and video:** the framing and how-it-works sections, the Results text, the title card and diagram, the second version of the video script, and the video (recorded by him, edited with Claude Code).

### Theo: the app

- **The app itself:** set up the Next.js app (TypeScript and Tailwind CSS) that every later screen was built on, deployed it to Vercel with Daniel, and checked the public link on a phone while signed out.
- **The first doctor screen:** one page per patient, opened from the web address; a warning banner at the top; a card for each fact with the critical facts (allergies and current medicines) first; disagreements between hospitals shown side by side; and a clear "No record found" page for an unknown patient. He built it against the sample record before the record format was confirmed, so the app was ready the moment real records arrived.
- **The older-record box:** when an older hospital record says "No current medications" but a later record lists a current medicine, that older line moves into a greyed history box instead of sitting next to the current list. It never applies to allergies or to lines that are part of a disagreement, and it keeps the hospital, date and exact quote.
- **"Who can confirm this":** with every warning, a box listing who could confirm the fact: the patient, the medicine's box, and each hospital with what its record says and an example contact (clearly labelled as made up, because the hospitals are made up). It gives options, never a recommendation: the doctor decides.
- **Write-up and review:** the first skeleton of the write-up, with an owner for each section and a checklist of the hackathon rules; the first credits list, with links and versions; and a review of the write-up and video script that caught gaps in the credits and wording.

## How commits are credited

From early in the project, our rule (written in CLAUDE.md) has been:

- Every commit is authored by the team member whose computer made it, using their own git name and email.
- Claude is added as co-author with a Co-Authored-By line at the end of the commit message. Commits are never authored as Claude.
- When one of us built a task for another teammate who was away, the commit is authored by the person who pushed it, and our task tracker records whose task it was.

The early commits that show "Claude" as the author were made before this rule was in place. Commit history is never rewritten, so they stay as they are; the sections above say who was responsible for that work.
