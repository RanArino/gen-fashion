#!/usr/bin/env python3
"""MR-6 ranking-change proof: does the intent boost actually change output?

Tags a fixed, hard-coded subset of items in the shared demo closet's
adult-01 wardrobe (real seeded data, not a throwaway fixture -- the same
tagged items double as 90-second demo material), then runs
adk-agent-service's search_closet three times against a live `make dev`
Elasticsearch: boost-on with intent A, boost-off, and boost-on with a
different intent B. Asserts all three of:

  1. run 2 (boost-off) differs from run 1 (boost-on/intent A) -- the boost
     changes the result at all.
  2. the TOP-N SET (membership, not just internal order) differs between
     run 1 and run 2 -- a reshuffle confined to the tail is invisible to a
     user.
  3. run 3 (boost-on/intent B) differs from run 1 -- two different intents
     must produce two different orders, or the clause is matching tag
     presence rather than intent.

Exits non-zero if any assertion fails, printing all three orders side by
side. Writes the same orders to an evidence file.

Idempotent per the plan's "Idempotence and Recovery" section: FIXTURE_ITEMS
below is a hard-coded, fixed list of adult-01 item ids. Re-running sets the
same tags on the same items -- it creates nothing, and never clears tags on
exit (the demo depends on the tagging staying durable). It fails rather than
silently skips if a fixture id is missing from the index, since a silently
skipped item would weaken the fixture without failing the proof.

Run against a live `make dev` stack:

    python3 scripts/mr6_intent_ranking_proof.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adk-agent-service"))

from elasticsearch import Elasticsearch  # noqa: E402

from styling_app.config import get_settings  # noqa: E402
from styling_app.tools.search_closet import search_closet  # noqa: E402

SHARED_CLOSET_ID = "adult-01"
DESCRIPTION = "white shirt"
INTENT_A = "CONFIDENT"
INTENT_B = "PROTECTED"
LIMIT = 5

# Fixed adult-01 item ids (discovered once against the running shared-closet
# seed and hard-coded here, per the plan's idempotence requirement). All are
# plausible answers to DESCRIPTION at baseline: the four Shirt items score
# highest via the "shirt"/"white" should-clauses, and the two Dress items
# below sit just past the baseline top-5 boundary (see script docstring for
# derivation) -- comparable data, not cherry-picked to fabricate a change.
FIXTURE_ITEMS = {
    # Baseline (untagged) top-5 for DESCRIPTION against adult-01, for
    # reference/verification only -- this script does not tag these:
    #   1. 973ecde5-2c98-5cfd-9a78-66946afb61a2  Shirt
    #   2. fd13c44a-727e-5b6e-bdb5-28e993c7ed51  Shirt
    #   3. 7342e5e0-ed3d-58e5-9967-7f2fd025e497  Shirt
    #   4. 40646b57-f39b-5bd1-908f-46ef58a7078e  Shirt
    #   5. f7c9bb60-072e-5ebd-889f-fcb5fa5e5a3c  Dress  <- displaced by INTENT_A tag
    "ca39ca35-03f7-5667-b9a7-82e35e8b14c1": [INTENT_A],  # Dress, baseline rank 6
    "20f2fa1d-7ed7-5614-a6d8-d84859f59f01": [INTENT_B],  # Dress, baseline rank 8
}


def _tag_fixture(client: Elasticsearch, index: str) -> None:
    """Apply FIXTURE_ITEMS' intent tags. Fails loudly if an id is missing."""
    for item_id, tags in FIXTURE_ITEMS.items():
        if not client.exists(index=index, id=item_id):
            raise RuntimeError(
                f"Fixture item {item_id} not found in index {index!r} -- "
                "the shared closet seed may be missing or different from "
                "what this script was written against. Re-seed with "
                "`make seed` or update FIXTURE_ITEMS."
            )
        client.update(index=index, id=item_id, doc={"intentTags": tags})
    client.indices.refresh(index=index)


def _run_search(intent: str | None, boost_enabled: bool) -> list[str]:
    # get_settings() is @lru_cache'd, so this is the one live Settings
    # instance hybrid_search reads. Flip its flag for the duration of this
    # call only, then restore it -- other code in this process must not see
    # a different config permanently.
    settings = get_settings()
    original_flag = settings.intent_boost_enabled
    settings.intent_boost_enabled = boost_enabled
    try:
        hits = search_closet(
            description=DESCRIPTION,
            source="SHARED_CLOSET",
            user_id="proof-script",
            shared_closet_id=SHARED_CLOSET_ID,
            intent=intent,
            limit=LIMIT,
        )
    finally:
        settings.intent_boost_enabled = original_flag
    return [hit["item_id"] for hit in hits]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MR-6 ranking-change proof.")
    parser.add_argument("--evidence-dir", default="/tmp/mr6-evidence")
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    client = Elasticsearch(hosts=[settings.elasticsearch_url])
    index = settings.clothing_items_index

    print(f"Tagging fixture items in index {index!r} …")
    _tag_fixture(client, index)

    print(f"Run 1: boost-on, intent={INTENT_A!r}")
    run1 = _run_search(intent=INTENT_A, boost_enabled=True)
    print(f"  {run1}")

    print("Run 2: boost-off (same query)")
    run2 = _run_search(intent=INTENT_A, boost_enabled=False)
    print(f"  {run2}")

    print(f"Run 3: boost-on, intent={INTENT_B!r}")
    run3 = _run_search(intent=INTENT_B, boost_enabled=True)
    print(f"  {run3}")

    evidence = {
        "description": DESCRIPTION,
        "shared_closet_id": SHARED_CLOSET_ID,
        "limit": LIMIT,
        "fixture_items": FIXTURE_ITEMS,
        "run1_boost_on_intent_a": run1,
        "run2_boost_off": run2,
        "run3_boost_on_intent_b": run3,
    }

    failures = []
    if run2 == run1:
        failures.append("run 2 (boost-off) is identical to run 1 (boost-on) -- boost has no effect")
    if set(run1) == set(run2):
        failures.append(
            "top-N SET is identical between run 1 and run 2 (only internal order may have "
            "changed, if at all) -- a tail reshuffle is not visible to a user"
        )
    if run3 == run1:
        failures.append(
            f"run 3 (intent={INTENT_B!r}) is identical to run 1 (intent={INTENT_A!r}) -- "
            "the clause is matching tag presence, not intent"
        )

    evidence["failures"] = failures
    (evidence_dir / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(f"\nEvidence written to {evidence_dir / 'evidence.json'}")

    print("\n--- Orders side by side ---")
    print(f"run1 (boost-on,  intent={INTENT_A}): {run1}")
    print(f"run2 (boost-off, intent={INTENT_A}): {run2}")
    print(f"run3 (boost-on,  intent={INTENT_B}): {run3}")

    if failures:
        print("\nFAILED assertions:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nAll assertions passed: the intent boost changes ranking output.")


if __name__ == "__main__":
    main()
