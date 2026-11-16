# Handover: credits

Every dataset, model, library and AI tool we used, with a link. This file matches the Sources table in the write-up (Google Doc **Handover write-up**, https://docs.google.com/document/d/1lHzcvi0vvmdCBLFHJB3e1dCduw-LKhDw7dX_G8oRlHE/edit). Updated 15 Nov 2026; if the two ever differ, the write-up wins.

## Data

| What | Used for | Link |
| --- | --- | --- |
| Synthea CSV sample, Nov 2021 | The 180 synthetic patients (20 working, 160 held-out) | https://synthea.mitre.org/downloads |
| Synthea paper: Walonoski et al., JAMIA 25(3), 2018 | Citation for Synthea | https://doi.org/10.1093/jamia/ocx079 |
| Synthea (the patient generator, by MITRE) | The tool that made the synthetic patient sample | https://github.com/synthetichealth/synthea |
| MTSamples (Medical Transcriptions, Kaggle; CC0 licence) | 12 hand-labelled notes in real doctors' style | https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions |
| MTSamples copy in the salgadev/medical-nlp repository (GPL-3.0) | The copy of the MTSamples file (mtsamples.csv) we took the 12 notes from | https://github.com/salgadev/medical-nlp |

## Models and AI tools

| What | Used for | Link |
| --- | --- | --- |
| Claude (Anthropic): Sonnet 5.5 (`claude-sonnet-5-5`) and Haiku 5.5 (`claude-haiku-5-5`) via the Claude API | Sonnet 5.5 is the extraction model; Haiku 5.5 is the comparison row | https://docs.claude.com |
| Anthropic Python library (anthropic 2.8.0) | How our code sends each record to Claude | https://github.com/anthropics/anthropic-sdk-python |
| Claude and Claude Code (Anthropic) | Coding assistant and planning help; also edited the demo video | https://claude.com/product/claude-code |
| Paradev (formerly Superset), Superset Inc. | Running several Claude Code sessions side by side, each in its own copy of the code | https://paradev.com |
| Microsoft Azure AI Language, Text Analytics for Health | Extra comparison on the 160 held-out patients (allergies and medicines), free tier, API version 2023-04-01, model version 2023-12-01 | https://learn.microsoft.com/en-us/azure/ai-services/language-service/text-analytics-for-health/overview |
| medSpaCy 1.3.1 | Second baseline (rule-based medical text reader), compared on extraction | https://github.com/medspacy/medspacy |

## Libraries, platforms and standards

| What | Used for | Link |
| --- | --- | --- |
| pandas | Reading and trimming the Synthea files | https://pandas.pydata.org |
| NumPy | Used by pandas for the Synthea tables | https://numpy.org |
| jsonschema | Checking every record matches our format | https://python-jsonschema.readthedocs.io |
| pytest 9.2.0 | Running the automated checks on our code | https://docs.pytest.org |
| Next.js | The app | https://nextjs.org |
| React 19 | The building blocks of the app's pages (used by Next.js) | https://react.dev |
| Tailwind CSS | Styling for the app's pages | https://tailwindcss.com |
| Vercel | Hosting the app | https://vercel.com |
| Lexend font (Google Fonts), SIL Open Font License 1.1 | Font for all text in the app | https://fonts.google.com/specimen/Lexend |
| GitHub | Code repository | https://github.com/blueslick/Veritas-AI-Hackathon- |
| ffmpeg (installed as ffmpeg-full with Homebrew) | Editing the demo video: cuts, captions, zoom, red boxes, sound levelling, export | https://ffmpeg.org |
| qrencode | Making the QR code for the app link | https://fukuchi.org/works/qrencode/ |
| whisper.cpp | Timing the voiceover words so captions and red boxes line up | https://github.com/ggml-org/whisper.cpp |
| OpenAI Whisper, `small.en` model (run through whisper.cpp) | Used only to find word timings in my own voice recordings | https://github.com/openai/whisper |
| HL7 FHIR | Our record layout follows its allergy, medication and condition record types | https://hl7.org/fhir/ |

## Video

| What | Used for | Link |
| --- | --- | --- |
| Canva | Title card for the video; the background is a Canva stock photo of a hospital corridor | https://www.canva.com |

The video editing tool is added here and in the write-up once the video is made (T50).

## Existing tools we compared against (public pages, read 15 Nov 2026)

These are listed under the Sources table in the write-up: Particle Health Snapshot, Fierce Healthcare on Epic's AI summaries, Evidently, DrFirst medication history, and a TechTarget news report on a JAMA Network Open study of AI-written hospital discharge summaries.
