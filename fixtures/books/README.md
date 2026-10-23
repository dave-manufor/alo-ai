# Book ingestion fixtures

`raw/` contains local copies of open-license/public-domain book files used for ingestion testing. It is intentionally gitignored because the source archives and ebooks are large and their redistribution terms vary by jurisdiction.

The tracked [`manifest.json`](manifest.json) records the requested title, verified source title, source URL, download URL, format, license/rights note, attribution, and local path. Run ingestion against `fixtures/books/raw/`.

Two requested entries remain pending because the pasted list does not identify an exact work: `nursery-rhymes-illustrated-fables` and `tortoise-and-the-baboon-folktales`. The latter has a closest verified African Storybook match recorded in the manifest, but it is not silently treated as the requested title.
