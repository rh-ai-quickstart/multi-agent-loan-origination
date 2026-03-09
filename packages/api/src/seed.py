# This project was developed with assistance from AI tools.
"""CLI entrypoint for demo data seeding.

Usage:
    python -m src.seed          # Seed demo data
    python -m src.seed --force  # Clear and re-seed
"""

import argparse
import asyncio
import json
import sys

from db.database import ComplianceSessionLocal, SessionLocal

from .services.seed.seeder import seed_demo_data


async def main(force: bool = False) -> None:
    """Run demo data seeding."""
    async with SessionLocal() as session:
        async with ComplianceSessionLocal() as compliance_session:
            result = await seed_demo_data(session, compliance_session, force=force)
            print(json.dumps(result, indent=2, default=str))

            if result.get("status") == "already_seeded":
                print("\nDemo data already seeded. Use --force to re-seed.")
                sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear existing demo data and re-seed",
    )
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
