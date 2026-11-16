# Handover: sources

Every outside dataset, model, library, tool and article we used, with a link. This is the full list behind the Sources line in the [README](../README.md). Who wrote which part of our own code is in [credits.md](credits.md). Links were last opened on 16 Nov 2026.

## Data

| What | Used for | Link |
| --- | --- | --- |
| Synthea CSV sample, Nov 2021 | The 180 synthetic patients we scored (20 working, 160 held-out) | https://synthea.mitre.org/downloads |
| Synthea (the patient generator, by MITRE) | The tool that made the synthetic patient sample | https://github.com/synthetichealth/synthea |
| Synthea paper: Walonoski et al., JAMIA 25(3), 2018 | Citation for Synthea | https://doi.org/10.1093/jamia/ocx079 |
| MTSamples (Medical Transcriptions, Kaggle; CC0 licence; originally from mtsamples.com) | 12 hand-labelled notes in real doctors' writing style | https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions |
| MTSamples copy in the salgadev/medical-nlp repository (GPL-3.0) | The copy of the MTSamples file (mtsamples.csv) we took the 12 notes from | https://github.com/salgadev/medical-nlp |

The demo patient, the hospital record templates, the 40 trap notes and every answer key were written by us.

## Models and AI tools

| What | Used for | Link |
| --- | --- | --- |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) and Claude Haiku 5.5 (`claude-haiku-5-5`), Anthropic, via the Claude API | Sonnet 5.5 reads the hospital records (our tool); Haiku 5.5 is a cheaper comparison | https://docs.claude.com |
| Anthropic Python library (anthropic 2.8.0) | How our code sends each record to Claude | https://github.com/anthropics/anthropic-sdk-python |
| Claude and Claude Code (Anthropic) | Coding assistant, planning, design mock-ups, writing help and video editing | https://claude.com/product/claude-code |
| Paradev (formerly Superset) | Running several Claude Code sessions side by side, each in its own copy of the code | https://paradev.com |
| Microsoft Azure AI Language, Text Analytics for Health (free tier; API version 2023-04-01, model version 2023-12-01) | Extra comparison on the 160 held-out patients, allergies and medicines only | https://learn.microsoft.com/en-us/azure/ai-services/language-service/text-analytics-for-health/overview |
| Claude Fable (Anthropic) | An outside review of the write-up and video script, and suggestions for the app's design | https://www.anthropic.com/claude |
| ChatGPT (OpenAI) | Research on what makes a good hackathon demo video (advice from past winners and judges on Reddit and Devpost), used as tips for our video | https://chatgpt.com |
| Agentation (Benji Taylor) | Clicking parts of the app on a laptop to leave notes that Claude Code then read and acted on, during app reviews | https://github.com/benjitaylor/agentation |
| medSpaCy 1.3.1 | Second baseline: a rule-based medical text reader, compared on extraction | https://github.com/medspacy/medspacy |

## Libraries, platforms and standards

| What | Used for | Link |
| --- | --- | --- |
| Python | The data scripts, the tool and the scoring | https://www.python.org |
| pandas | Reading and trimming the Synthea files | https://pandas.pydata.org |
| NumPy | Used with pandas when picking the patients from the Synthea tables | https://numpy.org |
| jsonschema | Checking every record matches our format | https://python-jsonschema.readthedocs.io |
| httpx | Sending our records to Azure for the comparison | https://www.python-httpx.org |
| pytest 9.2.0 | Running the automated checks on our code | https://docs.pytest.org |
| Next.js | The app | https://nextjs.org |
| React 19 | The building blocks of the app's pages (used by Next.js) | https://react.dev |
| Tailwind CSS | Styling for the app's pages | https://tailwindcss.com |
| IBM Plex Sans and IBM Plex Mono (IBM), SIL Open Font License 1.1; the font files are included in the app | Fonts for the app: Plex Sans for all text, Plex Mono for the original record text | https://fonts.google.com/specimen/IBM+Plex+Sans |
| Vercel | Hosting the app | https://vercel.com |
| GitHub | Code repository | https://github.com/blueslick/Veritas-AI-Hackathon- |
| HL7 FHIR | Our record layout follows its allergy, medication and condition record types | https://hl7.org/fhir/ |

## Video

| What | Used for | Link |
| --- | --- | --- |
| Claude Code (Anthropic) | Edited the video from a written plan: chose the cuts, captions, zooms and outline boxes, and ran the tools below | https://claude.com/product/claude-code |
| FFmpeg | Cutting and joining the screen recordings, captions, zooms, red outline boxes, sound levelling and the final MP4 | https://ffmpeg.org |
| whisper.cpp | Timing the voiceover words so the captions and red outline boxes line up | https://github.com/ggml-org/whisper.cpp |
| OpenAI Whisper, `small.en` model (run through whisper.cpp) | Used only to find the word timings in Daniel's own voice recording | https://github.com/openai/whisper |
| qrencode | The QR code for the app's link at the end of the video | https://fukuchi.org/works/qrencode/ |
| Homebrew | Installing FFmpeg and qrencode on a Mac | https://brew.sh |
| Canva | Title card for the video; the background is a Canva stock photo of a hospital corridor | https://www.canva.com |

The voiceover is Daniel's own voice; no AI voice was used.

## Existing tools and the study we compared against (public pages, read 15 Nov 2026)

| What | What it supports in the write-up | Link |
| --- | --- | --- |
| Particle Health Snapshot | AI summaries of a patient's medical records | https://docs.particlehealth.com/docs/particle-snapshot |
| Particle Health Snapshot: AI summary | The summary itself (longitudinal patient summary) | https://docs.particlehealth.com/docs/particle-snapshot#longitudinal-patient-summary |
| Particle Health: Accessing Snapshot via API | Summary statements can carry citations back to the source records | https://docs.particlehealth.com/docs/accessing-snapshot-via-api |
| Fierce Healthcare on Epic's AI summaries | Epic's AI summaries include records from other hospitals (Care Everywhere) | https://www.fiercehealthcare.com/health-tech/epic-expands-ai-ambitions-agent-platform-cosmos-powered-predictions-and-deeper-workflow |
| Evidently (AMIA partner page) | AI summaries of patient records | https://amia.org/membership/partners/evidently |
| DrFirst medication history | AI fills in missing prescription instructions | https://drfirst.com/blog/how-hospitals-reduce-medication-errors |
| TechTarget news report on a JAMA Network Open study of AI-written hospital discharge summaries | Why leaving facts out matters: doctors flagged omissions in 25% of the summaries they reviewed and made-up facts in 2% (figures as reported by TechTarget; we read the report, not the study) | https://www.techtarget.com/searchhealthit/news/366642890/Agentic-AI-discharge-summaries-linked-to-safety-clinician-wellbeing |
