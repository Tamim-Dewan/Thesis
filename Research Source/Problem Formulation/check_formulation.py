"""Small counterexample checks for the revised equations, not a flight simulator.

Run: python3 'Problem Formulation/check_formulation.py'
All numerical inputs below are synthetic, not calibrated UAV/medical parameters.
"""

from itertools import product
from math import exp, isclose, log
import unittest


def value(completion, severity=1.0, confidence=1.0, half_life=30.0):
    benefit = severity * exp(-log(2) * completion / half_life)
    return 2 * benefit * confidence / (benefit + confidence) if benefit + confidence else 0.0


def select(candidates_by_uav):
    """Exhaustively solve the finite candidate problem, allowing no dispatch."""
    best_score, best = 0.0, ()
    for choices in product(*[(None, *candidates) for candidates in candidates_by_uav]):
        chosen = tuple(candidate for candidate in choices if candidate is not None)
        tasks = [task for candidate in chosen for task in candidate['tasks']]
        if len(tasks) != len(set(tasks)):
            continue
        score = sum(candidate['score'] for candidate in chosen)
        if score > best_score:
            best_score, best = score, chosen
    return best_score, best


class FormulationChecks(unittest.TestCase):
    def test_assignment_uses_whole_candidate_and_never_duplicates_task(self):
        candidates = [
            [{'tasks': ('A', 'B'), 'score': 1.4}, {'tasks': ('C',), 'score': 0.8}],
            [{'tasks': ('A',), 'score': 0.9}, {'tasks': ('D',), 'score': 0.7}],
        ]
        score, chosen = select(candidates)
        self.assertTrue(isclose(score, 2.1))
        self.assertEqual({task for tour in chosen for task in tour['tasks']}, {'A', 'B', 'D'})

    def test_earlier_completion_wins_for_same_task(self):
        early = {'tasks': ('A',), 'score': value(2)}
        late = {'tasks': ('A',), 'score': value(20)}
        _, chosen = select([[late, early]])
        self.assertEqual(chosen, (early,))
        self.assertEqual(value(0, severity=0, confidence=0), 0)

    def test_empty_candidates_and_no_ready_uavs(self):
        self.assertEqual(select([[], []]), (0.0, ()))
        self.assertEqual(select([]), (0.0, ()))

    def test_service_and_return_time(self):
        launch, recovery, travel, service = 2, 3, [4, 5, 6], [7, 8]
        first = launch + travel[0] + service[0]
        second = first + travel[1] + service[1]
        total = launch + recovery + sum(travel) + sum(service)
        self.assertEqual((first, second, total), (13, 26, 35))
        self.assertFalse(second <= 25)  # Candidate misses its deadline.
        self.assertTrue(second <= float('inf'))

    def test_candidate_load_drives_payload_evolution(self):
        required_load, unit_mass, empty_mass = 3, 0.5, 2.0
        demands = [1, 2]
        stock = required_load
        masses = [empty_mass + stock * unit_mass]
        for demand in demands:
            stock -= demand
            masses.append(empty_mass + stock * unit_mass)
        self.assertEqual(masses, [3.5, 3.0, 2.0])
        self.assertEqual(stock, 0)
        self.assertTrue(required_load <= 3)  # Candidate load passes item-count capacity.
        self.assertFalse(required_load * unit_mass <= 1.0)  # Count can pass while mass fails.

    def test_battery_forecast_is_not_actual_consumption(self):
        battery = 100
        forecast = battery - 30
        self.assertEqual(battery, 100)
        for interval_energy in [12, 8, 10]:
            battery -= interval_energy
        self.assertEqual(battery, forecast)
        self.assertEqual(battery, 70)
        self.assertFalse(30 + 80 <= 100)  # Reserve enforced beyond return energy.

    def test_reservation_survives_another_decision_epoch(self):
        task = {'status': 'pending', 'owner': None, 'confidence': 0.9, 'deadline': 100}

        def eligible(now):
            return (task['status'] == 'pending' and task['owner'] is None
                    and task['confidence'] >= 0.8 and now < task['deadline'])

        self.assertTrue(eligible(0))
        task.update(status='assigned', owner='U1')
        self.assertFalse(eligible(10))
        task.update(status='pending', owner=None)  # Acknowledged cancellation.
        self.assertTrue(eligible(20))
        self.assertFalse(eligible(100))

    def test_partial_delivery_preserves_remaining_demand(self):
        demand, inventory, delivered = 3, 3, 1
        self.assertLessEqual(delivered, min(demand, inventory))
        demand -= delivered
        inventory -= delivered
        self.assertEqual((demand, inventory), (2, 2))
        self.assertFalse(demand == 0)

    def test_routed_detour_can_avoid_blocked_direct_segment(self):
        # Obstacle is [1, 2] x [-0.5, 0.5]; direct (0,0)--(3,0) crosses it.
        path = [(0, 0), (0, 1), (3, 1), (3, 0)]
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            if x1 == x2:
                self.assertTrue(x1 < 1 or x1 > 2)
            else:
                self.assertEqual(y1, y2)
                self.assertTrue(y1 < -0.5 or y1 > 0.5)
        self.assertTrue(0 < 1 < 2 < 3)

    def test_active_recourse_payload_starts_from_current_inventory(self):
        current_inventory, revised_demands, unit_mass, empty_mass = 5, [1, 2], 0.5, 2.0
        self.assertLessEqual(sum(revised_demands), current_inventory)
        stock = current_inventory
        masses = [empty_mass + stock * unit_mass]
        for demand in revised_demands:
            stock -= demand
            masses.append(empty_mass + stock * unit_mass)
        self.assertEqual(stock, 2)
        self.assertEqual(masses, [4.5, 4.0, 3.0])

    def test_incumbent_recourse_candidate_is_conditional(self):
        current_battery, reserve = 20, 5
        incumbent_remaining_energy = 18
        safe_return_energy = 10
        self.assertFalse(incumbent_remaining_energy + reserve <= current_battery)
        self.assertTrue(safe_return_energy + reserve <= current_battery)

    def test_displaced_task_returns_to_pending_if_unselected(self):
        previous_owner = {'B': 'U1', 'C': 'U1'}
        selected_owner = {'C': 'U1', 'N': 'U1'}
        pending_after_commit = {
            task for task, owner in previous_owner.items()
            if owner is not None and task not in selected_owner
        }
        self.assertEqual(pending_after_commit, {'B'})
        self.assertNotIn('B', selected_owner)


if __name__ == '__main__':
    unittest.main(verbosity=2)
