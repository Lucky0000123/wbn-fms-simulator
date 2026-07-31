"""Gate J59: regenerating identical results must not churn the working tree.

data/simulator_model_results.json is committed as reference and is rewritten by
every retrain, which the harness performs. It stamped a fresh `generated_at`
onto byte-identical results, so `git status` was dirty after every verification
run. That is not cosmetic: once the tree is always dirty, `git status` stops
being a signal and a genuine accidental change hides in the noise.

simulator_model.preserve_stamp() carries the old stamp forward when nothing else
moved. This gate tests that function directly rather than running a ~1 minute
retrain twice, so it costs milliseconds.

The subtle case, and the one that would have made the fix a no-op: `prev` has
been through JSON and `out` has not. A numpy float, a tuple or a Decimal in
`out` does not compare equal to its round-tripped self, so a naive dict
comparison always reports "changed" and the stamp always moves. The comparison
is on serialised text for exactly this reason, and the round-trip cases below
are the point of this file.
"""
import json
import sys

from simulator_model import preserve_stamp

FAILED = []
OLD, NEW = "2020-01-01T00:00:00+00:00", "2099-12-31T23:59:59+00:00"


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def roundtrip(d):
    """What actually lands on disk and comes back on the next run."""
    return json.loads(json.dumps(d, default=str))


print("=== identical results keep the old stamp ===")

base = {"generated_at": OLD, "best_r2": 0.4792, "routes": 36,
        "models": {"a": {"r2": 0.5, "mae": 31.88}}, "served": False}

out = dict(base, generated_at=NEW)
kept = preserve_stamp(roundtrip(base), out)
check("returns True when unchanged", kept)
check("stamp carried forward", out["generated_at"] == OLD, out["generated_at"])

print("\n=== a real change still moves the stamp ===")

for field, mutate in [
    ("a metric", lambda d: d.update(best_r2=0.4801)),
    ("a nested metric", lambda d: d["models"]["a"].update(mae=99.9)),
    ("a new key", lambda d: d.update(new_key=1)),
    ("a removed key", lambda d: d.pop("served")),
    ("a bool flipped", lambda d: d.update(served=True)),
]:
    out = json.loads(json.dumps(base))
    out["generated_at"] = NEW
    mutate(out)
    kept = preserve_stamp(roundtrip(base), out)
    check("%s moves the stamp" % field,
          (not kept) and out["generated_at"] == NEW, out["generated_at"])

print("\n=== JSON round-trip must not be mistaken for a change ===")

# These are the shapes that appear in the real payload and that a naive
# dict-equality check would report as changed on every single run.
import decimal                                                    # noqa: E402

tricky = {"generated_at": OLD,
          "tuple_becomes_list": (1, 2, 3),
          "decimal": decimal.Decimal("1.5"),
          "nested": {"t": (4, 5)}}
out = dict(tricky, generated_at=NEW)
kept = preserve_stamp(roundtrip(tricky), out)
check("tuples/Decimals round-tripping is NOT treated as a change", kept,
      "stamp=%s" % out["generated_at"])
check("stamp preserved through round-trip", out["generated_at"] == OLD)

# Key ORDER must not matter: dict ordering is not a semantic change and json
# key order is not stable across versions.
shuffled = {k: tricky[k] for k in reversed(list(tricky))}
out = dict(tricky, generated_at=NEW)
check("key order is not a change", preserve_stamp(roundtrip(shuffled), out))

print("\n=== degenerate inputs must not crash or falsely preserve ===")

out = dict(base, generated_at=NEW)
check("no previous file -> stamp stands", not preserve_stamp(None, out)
      and out["generated_at"] == NEW)
out = dict(base, generated_at=NEW)
check("corrupt previous (a list) -> stamp stands", not preserve_stamp([], out))
out = dict(base, generated_at=NEW)
check("previous without the key -> stamp stands",
      not preserve_stamp({k: v for k, v in base.items() if k != "generated_at"}, out))

print()
if FAILED:
    print("J59 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("stamp stability gate passes")
