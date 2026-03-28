#!/usr/bin/env python3
"""Replay DLQ events from the execution-service outbox (future use).

Currently the execution-service uses direct Kafka publishing.  When the
outbox pattern is enabled, failed rows can be listed and manually replayed
using this script.

Usage:
    python scripts/replay_execution_outbox.py --db sqlite:///./execution_service.db
"""
import argparse
import json

from sqlalchemy import Column, String, Text, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class OutboxEvent(Base):
    __tablename__ = "execution_outbox"
    id = Column(String(36), primary_key=True)
    topic = Column(String(255))
    payload_json = Column(Text)
    status = Column(String(32))


def main() -> None:
    parser = argparse.ArgumentParser(description="List dead-letter outbox rows")
    parser.add_argument("--db", default="sqlite:///./execution_service.db")
    parser.add_argument("--status", default="dead", help="Filter by status")
    args = parser.parse_args()

    engine = create_engine(args.db)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        rows = db.execute(
            select(OutboxEvent).where(OutboxEvent.status == args.status)
        ).scalars().all()
        if not rows:
            print(f"No outbox rows with status={args.status}")
            return
        for row in rows:
            print(json.dumps({"id": row.id, "topic": row.topic, "payload": row.payload_json}))
    print(f"\nTotal: {len(rows)} row(s)")


if __name__ == "__main__":
    main()
