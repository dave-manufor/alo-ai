# Passage Generator (W2)

PRD 4.5, SDD 5. This folder holds the generator's code. So far it has the parts that need no model:

| Module | Does | PRD |
|---|---|---|
| `blueprint.py` | The READ blueprint table and the STANDARD / DEMO length rules `[CAL]` | 4.5 |
| `textlevel.py`, `syllables.py` | The rule-based ARL estimator: three features, the median `[CAL]` | 9.2 |
| `boundaries.py` | `PHRASE` / `CLAUSE` / `TERMINAL` after each token, from punctuation and a spaCy parse | 4.5 G3, 5.5 |
| `artifact.py` | Tokens, `text_content` and items in the passage schema's shape | 4.5 G3, 10.1 |
| `gate.py` | The nine code checks of the generation gate; each returns a name, pass or fail, and a reason | 4.5 G4 |
| `detail.py` | Re-checks the safe detail from the interest chat before the Writer sees it | 4.5 G1 |
| `names.py`, `text.py` | The name list and blocklist types; the clip store's word rule | 4.5, 4.6 |

The Writer, the Critic calls, the clip synthesis and the HTTP endpoint come in later PRs. The data files (taxonomy, names with IPA, blocklist, bank passages) come with the content PR.

## Run the tests

```
uv venv --python 3.11 services/core/generator/.venv
uv pip install --python services/core/generator/.venv/bin/python -r services/core/generator/requirements.txt pytest pytest-cov
services/core/generator/.venv/bin/python -m pytest -c services/core/generator/pyproject.toml services/core/generator
```

No cloud access is needed. Nothing here calls a model.
