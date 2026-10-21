# Passage Generator (W2)

PRD 4.5, SDD 5. This folder holds the generator's code. It has the code steps and, behind recorded responses in CI, the model steps:

| Module | Does | PRD |
|---|---|---|
| `blueprint.py` | The READ blueprint table and the STANDARD / DEMO length rules `[CAL]` | 4.5 |
| `textlevel.py`, `syllables.py` | The rule-based ARL estimator: three features, the median `[CAL]` | 9.2 |
| `boundaries.py` | `PHRASE` / `CLAUSE` / `TERMINAL` after each token, from punctuation and a spaCy parse | 4.5 G3, 5.5 |
| `artifact.py` | Tokens, `text_content` and items in the passage schema's shape | 4.5 G3, 10.1 |
| `gate.py` | The nine code checks of the generation gate; each returns a name, pass or fail, and a reason | 4.5 G4 |
| `detail.py` | Re-checks the safe detail from the interest chat before the Writer sees it | 4.5 G1 |
| `names.py`, `text.py` | The name list and blocklist types; the clip store's word rule | 4.5, 4.6 |
| `writer.py` | The Story Writer: the prompt, its output schema and one Gemini Flash call | 4.5 G2 |
| `critic.py` | The Critic: A answers from the story, B from the title and questions only (in parallel), C scores both against the rubrics | 4.5 G4 |
| `pipeline.py` | The loop: detail check, Writer, code gate, Critic, one retry inside the deadline, the passage document; `choose_listening` | 4.5, SDD 5 |
| `models.py` | Gemini on Vertex AI, or the recorded responses in `fixtures/ai/generator/` (`AI_MODE=fixtures`) | 4.5 |
| `clips.py` | Word clip URIs in the shared clip store, with the Session Agent's key rule | 4.5 G5 |
| `data.py`, `data/` | The curated names with IPA, the blocklist and the topic taxonomy, and their loaders | 4.5, 4.6 |

Making the missing clips (G5), storing the passage and the HTTP endpoint in Core come in later PRs.

**The name IPA is a draft.** PRD 4.6 says each name is checked by ear in the voice before it is used. Once text-to-speech is available, listen to every entry in `data/names.json` and remove any name that still sounds wrong.

## Run the tests

```
uv venv --python 3.11 services/core/generator/.venv
uv pip install --python services/core/generator/.venv/bin/python -r services/core/generator/requirements.txt pytest pytest-cov
services/core/generator/.venv/bin/python -m pytest -c services/core/generator/pyproject.toml services/core/generator
```

No cloud access is needed: the tests use scripted and recorded model answers.
