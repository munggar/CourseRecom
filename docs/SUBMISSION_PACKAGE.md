# Clean submission package

Create a reproducible source archive from the repository root:

```bash
python scripts/build_submission_zip.py
```

The archive is written to `out/CourseRecom-submission.zip`. You can choose another destination with `--output`.

The packager retains source code, tests, documentation, workflow files, and deployment configuration. It excludes Git history, Python virtual environments, node_modules, frontend build output, caches, logs, local database files, nested ZIP files, and actual `.env`/environment-secret files. Example templates ending in `.example` or `.sample` are retained.

Do not submit production credentials in a report or archive. Provide credentials separately through the institution's approved secret-sharing process only when required.
