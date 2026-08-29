# Local evaluation data

`public_set.jsonl` is copied byte-for-byte from the official Participant Kit and is intentionally versioned for local evaluation.

Download and extract the official [Participant Kit Release](https://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit), then copy its `data/catalog.jsonl` into this directory. The download is a one-time setup step; this project does not fetch data during installation or evaluation.

Verify the local file from the repository root:

```powershell
uv run python scripts\inspect_catalog.py data\catalog.jsonl
```

The validator expects 50,000 unique product identifiers and the official uncompressed SHA256 `da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67`. It exits without printing product records if validation fails.

`catalog.jsonl` and `catalog.jsonl.gz` are ignored by Git. Do not commit or redistribute them from this repository.
