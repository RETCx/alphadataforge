# Publishing AlphaDataForge

Activate the project Python environment and run commands from the repository root.

1. Update `project.version` in `pyproject.toml` for each new release.
2. Install release tools and run tests:

```powershell
python -m pip install -e ".[dev,publish]"
python -m pytest
```

3. Build into a version-specific folder and validate the distributions (replace
   `0.1.1` with the version being released):

```powershell
python -m build --outdir dist/0.1.1
python -m twine check --strict dist/0.1.1/*
```

Inspect the wheel and source archive before uploading. Do not include `.env`,
API keys, local datasets, or test recordings. Choose and add a license if you
want to grant explicit reuse rights; this project does not yet declare one.

4. Upload using a PyPI API token scoped to `alphadataforge`:

```powershell
python -m twine upload --username __token__ dist/0.1.1/*
```

Enter the token at the password prompt. Never commit it or paste it into chat.
PyPI does not allow replacing an uploaded file with the same filename; publish
changes under a new version instead.

Commit and push the corresponding source changes to GitHub separately. A PyPI
upload does not update the GitHub repository.

Official guide: https://packaging.python.org/en/latest/tutorials/packaging-projects/
