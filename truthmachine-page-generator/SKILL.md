---
name: truthmachine-page-generator
description: Generates static page JSON data for the TruthMachine UI by aggregating event and matrix data. Use when the matrix data has been updated and the UI needs to reflect the latest predictions and outcomes.
---

# TruthMachine Page Generator

This skill automates the consolidation of event metadata and forensic extractions into pre-processed JSON files used by the TruthMachine Next.js UI.

## Workflow

1.  **Consolidate Data**: The skill reads from `data/events/` and `data/atlas/` to match predictions with their corresponding ground-truth outcomes.
2.  **Generate JSON**: It creates or updates JSON files in `data/pages/` for every event.
3.  **UI Sync**: These files are directly consumed by the web frontend to render the "Accurate" vs "Inaccurate" source columns.

## Usage

Run the generator script providing the path to the project's data directory:

```bash
python3 scripts/generate_pages.py <path_to_data_dir>
```

The script will iterate through all events and generate the necessary page data.
