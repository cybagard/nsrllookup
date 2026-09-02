"""The lookup module (Seam 2): the highest point at which data-driven
**Known/Unknown/Invalid** behaviour is assertable without standing up HTTP.

One public function, ``look_up``, maps a request -- the digests, a single
**Algorithm**, and the current **Hash Set** -- to one **Lookup Result** per
digest, each carrying full **provenance**. A digest that is not well-formed for
its declared **Algorithm** is **Invalid**; a well-formed digest that is checked
and absent is **Unknown**; a present one is **Known**
(see ``.scratch/rds-v3-migration/spec.md`` -> API contract).
"""

from typing import Any
from typing import Dict
from typing import List

from hasheset import HashSet

# The hexadecimal length of a well-formed digest for each Algorithm.
DIGEST_LENGTH = {
    "md5": 32,
    "sha1": 40,
    "sha256": 64,
}


def is_well_formed(algorithm: str, digest: str) -> bool:
    """Whether ``digest`` is a well-formed hexadecimal value for
    ``algorithm`` -- the right length and all hex characters. A digest that
    fails this is **Invalid**: it was never a thing to check, distinct from
    **Unknown** (checked and absent).
    """
    if algorithm not in DIGEST_LENGTH:
        return False
    normalised = digest.upper()
    return (len(normalised) == DIGEST_LENGTH[algorithm]
            and all(char in "0123456789ABCDEF" for char in normalised))


def look_up(hash_set: HashSet, digests: List[str],
            algorithm: str) -> List[Dict[str, Any]]:
    """Return one **Lookup Result** per submitted **Digest**.

    Each result names its digest (normalised to UPPERCASE), the **Algorithm**,
    a **known**/**unknown**/**invalid** status scoped to that one **Algorithm**,
    and the **dataset** (Set, Release, applied Delta releases) that answered, so
    a forensic consumer knows exactly what the answer was checked against.
    """
    results = []
    dataset = hash_set.provenance.dataset()
    for raw_digest in digests:
        digest = raw_digest.upper()
        if not is_well_formed(algorithm, raw_digest):
            status = "invalid"
        elif hash_set.is_known(algorithm, digest):
            status = "known"
        else:
            status = "unknown"
        results.append({
            "digest": digest,
            "algorithm": algorithm,
            "status": status,
            "dataset": dataset,
         })
    return results
