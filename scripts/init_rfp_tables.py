"""Review additive PostgreSQL table DDL, or apply to the existing configured engine."""

import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from services.rfp_intake.models import Ticket, RFPMetadata, DepartmentSection, create_tables


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if args.apply:
        from services.database import engine

        create_tables(engine)
        print("Initialized missing RFP tables using the existing database engine.")
    else:
        for model in [Ticket, RFPMetadata, DepartmentSection]:
            print(str(CreateTable(model.__table__).compile(dialect=postgresql.dialect())) + ";")
            for index in model.__table__.indexes:
                print(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ";")


if __name__ == "__main__":
    main()
