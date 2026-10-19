"""Reporting package — business performance KPI endpoints.

Exposes the pipeline's output through three endpoints:
    - GET  /reporting/weekly-warehouse-client-performance
    - GET  /reporting/pipeline-runs/latest
    - POST /reporting/pipeline-runs

Imports flows and functions from ``data/pipelines/pipeline`` — pipeline logic
lives there, not here.
"""