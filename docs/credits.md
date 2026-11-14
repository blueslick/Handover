# Handover: credits

Every dataset, model, library and AI tool used, with a link. Draft started 14 Nov 2026 (T30). Finished in T46c.

How to use this file: a row is only "Checked" once someone has opened the link in a private window and confirmed we really used the thing. Remove any row for something that was cut.

## Data

| What | Used for | Link | Status |
| --- | --- | --- | --- |
| Synthea CSV sample, November 2021 (1,163 synthetic patients) | Source of the 100 patients (20 working, 80 held-out) | https://synthea.mitre.org/downloads | In use. Link to check |
| Synthea sample data repository | Where the same zip file can be downloaded | https://github.com/synthetichealth/synthea-sample-data | In use. Link to check |
| Synthea (the generator, by MITRE) | Credit for the tool that made the sample | https://github.com/synthetichealth/synthea | In use. Link to check |
| MTSamples medical transcriptions (Kaggle) | 12 notes labelled by hand, to test extraction on writing we did not produce | https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions | Only if T43 is done |

Synthea asks to be cited as: Walonoski J, et al. "Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record." Journal of the American Medical Informatics Association, 2018. Check the exact wording on the Synthea site before submitting.

## Models

| What | Used for | Link | Status |
| --- | --- | --- | --- |
| Claude API, model TBD (Sonnet 5.5 or Haiku 5.5, picked in T21) | Extracting facts from each hospital record | https://docs.claude.com | Fill in the exact model ID after T21 |

## AI tools used to build the project

| What | Used for | Link | Status |
| --- | --- | --- | --- |
| Claude Code | Writing and editing the pipeline and app code, directed and checked by the team | https://claude.com/claude-code | In use |
| Claude (chat) | Planning, task breakdown, reviewing documents | https://claude.ai | In use |

## Libraries and platforms

| What | Used for | Link | Status |
| --- | --- | --- | --- |
| Python 3.11+ | The pipeline | https://www.python.org | In use |
| pandas 3.0.5 | Reading and trimming the Synthea tables | https://pandas.pydata.org | In use |
| NumPy 2.5.3 | Used with pandas | https://numpy.org | In use |
| jsonschema 4.26.0 | Checking files against the record format | https://github.com/python-jsonschema/jsonschema | In use |
| Next.js 16 | The app | https://nextjs.org | In use |
| React 19 | The app | https://react.dev | In use |
| Tailwind CSS 4 | App styling | https://tailwindcss.com | In use |
| Vercel | Hosting the app | https://vercel.com | In use |
| GitHub | Code hosting | https://github.com/blueslick/Veritas-AI-Hackathon- | In use |
| medSpaCy | Second baseline, scored on extraction only | https://github.com/medspacy/medspacy | Only if T42 is done |

## Standards and background

| What | Used for | Link | Status |
| --- | --- | --- | --- |
| HL7 FHIR | Our record layout follows its allergy, medication and condition record types | https://hl7.org/fhir/ | Link to check |

## Still to add

- The two facts quoted in "The problem", each with its source link (Daniel, T46b).
- Any tutorial or code sample someone followed. Ask Abby and Daniel on Sunday evening.
- Tools for the video: screen recorder, editor, Canva for the diagram and title card (only the ones actually used).
- The drug list or brand-to-generic source, if it came from anywhere other than Synthea's own medicine names.
