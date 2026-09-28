# PGBM V2 recourse experiment evidence

This directory contains generated Version 2 evidence. The paired matrix has
one V1 row and one V2 row for every environment, task load, UAV count, and
seed combination. Decision traces are stored separately so that accepted and
rejected replacement decisions can be inspected without reconstructing them
from aggregate metrics.

The V2 contract is one-for-one active-mission task replacement. It uses the
current onboard inventory and existing collision-aware route builder. Reserve
inventory, base reload, and full fleet reoptimization are Version 3 scope.
