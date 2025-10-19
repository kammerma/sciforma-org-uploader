
from __future__ import annotations
import argparse
import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from .utils import build_graph_from_csv
from .sciforma_client import SciformaClient
from .module1_loader import resolve_or_create_ids
from .module2_orderer import enforce_ordering

# Load .env if present
load_dotenv()

app = FastAPI(title="Sciforma Organization Uploader", version="1.0.1")

# Global in-memory graph (lives for process lifetime)
ORG_GRAPH = None

def make_client(debug: bool = False) -> SciformaClient:
    base_url = os.environ.get('SCIFORMA_BASE_URL')
    token_url = os.environ.get('SCIFORMA_TOKEN_URL')
    client_id = os.environ.get('SCIFORMA_CLIENT_ID')
    client_secret = os.environ.get('SCIFORMA_CLIENT_SECRET')
    scope = os.environ.get('SCIFORMA_SCOPE', 'organizations:read organizations:write')
    timeout = int(os.environ.get('REQUEST_TIMEOUT_SECONDS', '30'))
    rate_limit_rps = os.environ.get('SCIFORMA_RATE_LIMIT_RPS')
    rate_limit_rps = float(rate_limit_rps) if rate_limit_rps else None

    missing = [k for k, v in {
        'SCIFORMA_BASE_URL': base_url,
        'SCIFORMA_TOKEN_URL': token_url,
        'SCIFORMA_CLIENT_ID': client_id,
        'SCIFORMA_CLIENT_SECRET': client_secret,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    return SciformaClient(base_url, token_url, client_id, client_secret, scope, timeout=timeout, debug=debug, rate_limit_rps=rate_limit_rps)


class Module1Request(BaseModel):
    csv_path: str
    simulation: bool = False
    debug: bool = False


class Module2Request(BaseModel):
    simulation: bool = False
    debug: bool = False
    print_structure: bool = False


class UploadOrgRequest(BaseModel):
    csv_path: str
    simulation: bool = False
    debug: bool = False
    print_structure: bool = False


@app.post('/module1')
def run_module1(req: Module1Request):
    global ORG_GRAPH
    try:
        graph = build_graph_from_csv(req.csv_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    client = make_client(debug=req.debug)
    found, created = resolve_or_create_ids(graph, client, simulation=req.simulation)
    ORG_GRAPH = graph
    return {
        'status': 'ok',
        'module': 1,
        'found_existing': found,
        'created_new': created,
        'total_nodes': len(graph.nodes),
    }


@app.post('/module2')
def run_module2(req: Module2Request):
    global ORG_GRAPH
    if ORG_GRAPH is None:
        raise HTTPException(status_code=400, detail='No in-memory graph. Run Module 1 first or use /upload-org.')
    client = make_client(debug=req.debug)
    processed = enforce_ordering(ORG_GRAPH, client, simulation=req.simulation)

    response = {
        'status': 'ok',
        'module': 2,
        'processed_nodes': processed,
        'total_nodes': len(ORG_GRAPH.nodes),
    }
    if req.print_structure:
        response['structure'] = ORG_GRAPH.as_list()
    return response


@app.post('/upload-org')
def upload_org(req: UploadOrgRequest):
    global ORG_GRAPH
    try:
        graph = build_graph_from_csv(req.csv_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    client = make_client(debug=req.debug)
    found, created = resolve_or_create_ids(graph, client, simulation=req.simulation)
    processed = enforce_ordering(graph, client, simulation=req.simulation)
    ORG_GRAPH = graph

    response = {
        'status': 'ok',
        'found_existing': found,
        'created_new': created,
        'processed_nodes': processed,
        'total_nodes': len(graph.nodes),
        'simulation': req.simulation,
    }
    if req.print_structure:
        response['structure'] = graph.as_list()
    return response


# Optional CLI entry point for convenience

def main():
    parser = argparse.ArgumentParser(description='Sciforma Organization Uploader')
    parser.add_argument('--csv', dest='csv_path', required=True, help='Path to CSV file')
    parser.add_argument('--simulation', action='store_true', help='Dry run (no writes)')
    parser.add_argument('--debug', action='store_true', help='Verbose API logging')
    parser.add_argument('--print-structure', action='store_true', help='Print in-memory structure at the end')
    args = parser.parse_args()

    client = make_client(debug=args.debug)
    graph = build_graph_from_csv(args.csv_path)
    found, created = resolve_or_create_ids(graph, client, simulation=args.simulation)
    processed = enforce_ordering(graph, client, simulation=args.simulation)

    result = {
        'found_existing': found,
        'created_new': created,
        'processed_nodes': processed,
        'total_nodes': len(graph.nodes),
        'simulation': args.simulation,
    }
    if args.print_structure:
        result['structure'] = graph.as_list()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
