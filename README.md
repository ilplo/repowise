# Repowise

Standalone source-of-truth repository for the Repowise application.

## Operating Model

Target repos keep their own `.repowise/` folders for:
- `wiki.db`
- `state.json`
- `config.yaml`
- generated editor files

Repowise is run against target repos explicitly, for example:

```bash
repowise init /path/to/target-repo
```

## Product Spec
- `PROD_SPEC.md`
