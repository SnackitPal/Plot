"""
PLOT / The Cultural Atlas - Command Line Interface
Provides convenient developer commands to seed the database, run bridging consensus,
and inspect geospatial hex distributions.
"""

import sys
import argparse

# Ensure UTF-8 output encoding on Windows if supported
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from atlas.storage.database import AtlasDatabase
from atlas.algorithms.bridging import CommunityNotesMF
from atlas.geo.hexgrid import AtlasHexGrid


def seed_database(db: AtlasDatabase):
    print("[*] Seeding PLOT database with initial ritual slates and diagnostics...")
    db.create_slate("slate_2026_09_04", "2026-09-04", "The Daily Slate #42")

    # Question 1: Mobility
    q1 = "q_mobility_01"
    db.add_question(
        q1,
        "slate_2026_09_04",
        1,
        "WORK & MOBILITY",
        "Would you accept a 30% pay cut if it guaranteed you would never have to commute again?",
    )
    db.add_choice("c1_a", q1, "A", "Yes, without hesitation.", "circle", "#FF5E3A")
    db.add_choice("c1_b", q1, "B", "No, income comes first.", "triangle", "#3A86FF")
    db.add_choice("c1_c", q1, "C", "Only if commute was >60 mins.", "square", "#00B4D8")
    db.add_choice("c1_d", q1, "D", "I prefer commuting / office life.", "diamond", "#7209B7")

    # Pre-seed realistic geographic distribution across macro hex cells
    grid = AtlasHexGrid(resolution=3)
    # Major global cities -> Hex cells
    cities = {
        "sf": (37.7749, -122.4194),
        "nyc": (40.7128, -74.0060),
        "london": (51.5074, -0.1278),
        "tokyo": (35.6762, 139.6503),
        "berlin": (52.5200, 13.4050),
        "sao_paulo": (-23.5505, -46.6333),
        "sydney": (-33.8688, 151.2093),
        "mumbai": (19.0760, 72.8777),
    }

    for name, (lat, lng) in cities.items():
        cell = grid.latlng_to_cell(lat, lng)
        db.record_hex_vote(q1, cell, "A", increment=120)
        db.record_hex_vote(q1, cell, "B", increment=80)
        db.record_hex_vote(q1, cell, "C", increment=45)
        db.record_hex_vote(q1, cell, "D", increment=15)

    # Seed perspectives for bridging deliberation
    p1 = "p_commute_time"
    db.add_perspective(
        p1,
        q1,
        "A",
        "Two hours in traffic every day strips away 500 hours a year of life you never get back.",
        "author_hash_west",
    )
    p2 = "p_income_priority"
    db.add_perspective(
        p2,
        q1,
        "B",
        "In a high-inflation housing market, sacrificing 30% salary permanently delays retirement and security.",
        "author_hash_east",
    )

    # Seed ratings
    for i in range(1, 10):
        db.rate_perspective(p1, f"rater_optA_{i}", 1.0)
        db.rate_perspective(p1, f"rater_optB_{i}", 0.8)  # Cross-agreement!
        db.rate_perspective(p2, f"rater_optB_{i}", 1.0)
        db.rate_perspective(p2, f"rater_optA_{i}", 0.1)  # Polarized!

    print("[OK] Seed completed successfully.")


def run_bridging(db: AtlasDatabase):
    print("[*] Running Community Notes Matrix Factorization Bridging Analysis...")
    ratings = db.get_all_ratings_for_question("q_mobility_01")
    if not ratings:
        print("No ratings found. Run 'python -m atlas.cli seed' first.")
        return

    model = CommunityNotesMF(
        n_factors=1,
        learning_rate=0.08,
        n_epochs=60,
        helpfulness_threshold=0.65,
        polarization_tolerance=0.35,
        min_ratings=5,
    )
    model.fit(ratings)
    evaluations = model.get_all_evaluations()

    print("\n--- PERSPECTIVE BRIDGING RESULTS ---")
    for ev in evaluations:
        print(f"[{ev.status:^18}] ID: {ev.perspective_id:<18} | Quality: {ev.intercept_quality:.2f} | Divergence: {ev.latent_factor:.2f} | Ratings: {ev.rating_count}")
    print("------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="PLOT: The Cultural Atlas CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("seed", help="Seed database with initial ritual questions and votes")
    subparsers.add_parser("bridge", help="Execute bridging consensus matrix factorization")

    args = parser.parse_args()
    db = AtlasDatabase("atlas.db")

    if args.command == "seed":
        seed_database(db)
    elif args.command == "bridge":
        run_bridging(db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
