# Contributing

Contributions are welcome when they keep the tool small, read-only against
NARA, and safe for archival research workflows.

## Development

```bash
python -m pip install -e '.[test]'
pytest
```

Live tests are opt-in:

```bash
RUN_NARA_INTEGRATION=1 pytest tests/integration
```

Live tests require `NARA_API_KEY` and should keep requests small.

## Pull Request Expectations

- Keep CLI, Python API, and MCP behavior routed through the shared service layer.
- Add or update offline unit tests for behavior changes.
- Do not commit API keys, downloaded private files, or user-specific research data.
- Preserve raw NARA responses when adding preservation workflows.
- Avoid broad refactors unless they directly support the change.

## Public Data And Attribution

This project is not affiliated with the National Archives and Records
Administration. Follow NARA's API terms, attribution guidance, and rate limits.
