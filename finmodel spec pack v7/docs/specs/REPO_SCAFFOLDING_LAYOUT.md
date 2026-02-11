# Repo scaffolding layout

Suggested structure:

```
finmodel/
  README.md
  pyproject.toml
  .env.example
  docs/
    specs/
      00_INDEX.md
      CURSOR_MASTER_PROMPT.md
      ARTIFACT_SCHEMAS/
      TEMPLATES/
        default_catalog.json
  apps/
    api/
      app/
        main.py
        routers/
        services/
        db/
          migrations/
            0001_init.sql
  shared/
    fm_shared/
      storage/
      validation/
      model/
      venture/
      analysis/
      scenarios/
      export/
  tests/
```
