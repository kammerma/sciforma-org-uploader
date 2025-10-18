# Sciforma Organization Uploader

FastAPI-based backend service to ingest an enterprise organization structure from CSV and load it into Sciforma via REST API.

## Overview

The service provides two core modules:

- **Module 1 (Loader)**: Parses a CSV containing the full path to each BSU (leaf) and builds an in-memory tree of organizational units. For each node, it checks Sciforma by *description*; if it exists, the `id` is filled. If missing and not in simulation mode, it creates the node in Sciforma and stores the returned `id`.
- **Module 2 (Orderer)**: Ensures sibling ordering in Sciforma by setting `next_sibling_id` on each node (and parent_id/name) using PATCH.

Both modules support:
- `simulation` (dry-run): no write calls (POST/PATCH) are performed; reads (GET) still occur.
- `debug`: log all Sciforma API calls and responses.

### Node shape (in-memory)
Each node conforms to:
```
{
  "parent_id": integer (int64),
  "previous_sibling_id": integer (int64),
  "name": string,
  "description": string,
  "id": integer (int64),
  "next_sibling_id": integer (int64)
}
```
- `description` is the code for the node (division_code, facility_code, department_code, bu_code, or bsu_code).
- `name` is the human-readable label (division, facility, department, bu, bsu).
- `parent_id` is the `id` of the immediate parent (or `-1` for top-level).
- `previous_sibling_id` / `next_sibling_id` are derived from sequential order per parent based on CSV order. Use `-10` when no previous/next sibling.

## CSV Format
Expected headers (sample included in `app/sample_data/sample_org.csv`):
```
division_code,division,facility_code,facility,department_code,department,bu_code,bu,bsu_code,bsu
```
Each row represents a leaf **BSU**; parents at each level are auto-inferred.

## Sciforma API
- **Search by description**: `GET {baseUrl}/organizations?description=<desc>&fields=description`
- **Create if missing**: `POST {baseUrl}/organizations`
  ```json
  { "parent_id": node_parent_id, "name": node_name, "description": node_description, "next_sibling_id": -10 }
  ```
- **Update ordering**: `PATCH {baseUrl}/organizations/:organization_id`
  ```json
  { "parent_id": node_parent_id, "name": node_name, "next_sibling_id": node_next_sibling_id }
  ```

### OAuth2 (Client Credentials)
Obtain access token from `SCIFORMA_TOKEN_URL` with `application/x-www-form-urlencoded` body:
- `grant_type=client_credentials`
- `client_id` (from Sciforma External Applications)
- `client_secret` (from Sciforma External Applications)
- `scope` (space-separated permissions)

The token is used as: `Authorization: Bearer <access_token>`.

> ⚠️ This service only requests a token on startup and refreshes it if a 401 is encountered.

## Project Structure
```
sciforma_org_uploader/
├─ app/
│  ├─ main.py                  # FastAPI app & endpoints
│  ├─ models.py                # Node models & constants
│  ├─ utils.py                 # CSV parsing and tree building
│  ├─ sciforma_client.py       # OAuth2 and Sciforma API client
│  ├─ module1_loader.py        # Module 1: create/resolve node IDs
│  ├─ module2_orderer.py       # Module 2: enforce ordering (PATCH)
│  └─ sample_data/
│     └─ sample_org.csv
├─ data/
├─ .env
├─ requirements.txt
├─ .gitignore
└─ README.md
```

## Quickstart

### 1) Python & Virtual Environment

```bash
python3.11 -m venv .venv
source .venv\Scripts\activate
```
Or

```bash
conda activate sciforma-org-uploader
```

### 2) Install Requirements
```bash
pip install -r requirements.txt
```

### 3) Run the API
```bash
uvicorn app.main:app --reload --port 8080
```

### 4) Endpoints

http://127.0.0.1:8080/docs

- **POST** `/upload-org`
  - Orchestrates Module 1 and Module 2 in one call.
  - Body (JSON):
    ```json
    {
      "csv_path": "app/sample_data/sample_org.csv",
      "simulation": true,
      "debug": false,
      "print_structure": true
    }
    ```
  - Response: summary and (optionally) the full in-memory structure.

- **POST** `/module1` (Module 1 only)
  ```json
  { "csv_path": "app/sample_data/sample_org.csv", "simulation": true, "debug": true }
  ```

- **POST** `/module2` (Module 2 only)
  ```json
  { "simulation": false, "debug": true, "print_structure": false }
  ```
  > Requires Module 1 to have been run in the current process to have an in-memory graph.

### Running as a Script (no HTTP)
```bash
python -m app.main --csv app/sample_data/sample_org.csv --simulation --print-structure
```

## Assumptions & Notes
- Codes are unique **per level** across the enterprise. If duplicates exist, refine the keys or include parent-code in uniqueness logic.
- Sibling order is defined by CSV row order per parent. If a parent appears multiple times, children are appended in encounter order.
- In **simulation** mode, missing nodes are *not* created, therefore `id` may be `None` and `next_sibling_id` may remain `-10` if the next sibling's ID is unknown.
- HTTP errors will be surfaced with context when `debug=true`.

## VS Code
- Python extension recommended.
- A basic `.env` is supported; `uvicorn` will read environment variables via the application code.