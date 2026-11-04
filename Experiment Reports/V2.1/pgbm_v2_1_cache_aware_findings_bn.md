# PGBM Initial Solution V2.1: cache aware recourse findings

এই report-টি V1 এবং V2 report-এর একই experiment flow অনুসরণ করে। V1 এবং canonical V2 evidence অপরিবর্তিত রাখা হয়েছে।

## V2.1-এর core feature

V2.1 হলো V2-এর উপর নির্মিত একটি bounded cache aware recourse layer। Ordinary V2 mission route তৈরি হওয়ার পরে dispatch time-এ সর্বোচ্চ একটি reserve parcel load করার চেষ্টা করা হয়। Payload slot, payload mass, full route energy, reserve energy, return route এবং ১২০ মিনিটের horizon feasible হলেই reserve load হয়।

Reserve parcel future undetected task দেখে নির্বাচন করা হয় না এবং flight-এর মাঝখানে reload করা হয় না। পরবর্তী replacement এখনও V2-এর one-for-one positive service-value gain rule অনুসরণ করে।

## Experiment-এর সংক্ষিপ্ত চিত্র

| বিষয় | ব্যবহৃত configuration |
| --- | --- |
| Environment | Synthetic এবং DU outdoor |
| Operation window | ১২০ মিনিট |
| Task load | ৩০, ৬০, ৯০ |
| UAV count | ৩, ৫, ৮, ১০ |
| Seed | ১০১–১১০ |
| Policies | V2 control, uniform, water heavy sensitivity |
| Evidence | ২৪০ scenario, ৭২০ metrics row, ২৪০ paired trace |
| Planner bound | max_pending_tasks=4, max_candidate_plans=5000 |

## Cache loading এবং hit mechanism

প্রথমে ordinary route calculate হয়। Route-এর পরে payload capacity থাকলে configured prior থেকে item নির্বাচন করা হয়। Selected item-এর জন্য payload, mass, energy margin, return time এবং horizon check করা হয়। Load হলে reserve inventory mission state-এ আলাদা থাকে। Replacement candidate-এর demand cache বা displaced task থেকে satisfy হলে cache evidence record হয়, কিন্তু positive gain এবং route feasibility ছাড়া সেটি accepted hit হিসেবে গণনা হয় না।

## Aggregate performance

| Variant | Episodes | Objective | Served | Delivery rate | Energy | Mean delay |
| --- | --- | --- | --- | --- | --- | --- |
| V2 control | 240 | 17.0110 | 27.3875 | 0.4817 | 5613.9421 | 18.2312 |
| Uniform cache | 240 | 17.2490 | 27.6750 | 0.4896 | 5679.4835 | 17.8556 |
| Water heavy sensitivity | 240 | 17.3388 | 27.8417 | 0.4925 | 5704.7735 | 18.0681 |

## Paired core findings

প্রতিটি V2.1 row একই environment, task load, UAV count এবং seed-এর V2 control row-এর সঙ্গে তুলনা করা হয়েছে।

| Variant | Paired episodes | Δ objective | Δ served | Δ deferred | Δ delay | Δ delivery | Δ energy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Uniform cache | 240 | 0.2380 | 0.2875 | -0.2875 | -0.3756 | 0.0078 | 65.5414 |
| Water heavy sensitivity | 240 | 0.3278 | 0.4542 | -0.4542 | -0.1631 | 0.0108 | 90.8314 |

**Core finding:** দুইটি one-slot policy-তেই objective সামান্য বেড়েছে। Uniform policy-তে mean objective gain 0.238 এবং served task gain 0.288। Water heavy sensitivity-তে gain 0.328 এবং 0.454। তবে reserve load-এর বড় অংশ unused অবস্থায় return করেছে এবং water heavy policy-তে cache energy overhead বেশি।

## Cache behavior

| Variant | Loaded | Used | Returned | Accepted hits | Hit rate | Cache energy overhead |
| --- | --- | --- | --- | --- | --- | --- |
| Uniform cache | 12.6333 | 1.4375 | 11.1958 | 1.4375 | 0.1428 | 45.7640 |
| Water heavy sensitivity | 12.4750 | 1.4792 | 10.9958 | 1.4792 | 0.1479 | 89.5940 |

এখানে hit rate হলো accepted cache hits divided by all accepted replacements। Loaded parcel-এর মধ্যে ব্যবহৃত fraction নয়।

## Environment sensitivity

| Environment | Variant | Hit rate | Cache energy overhead |
| --- | --- | --- | --- |
| Synthetic | Uniform cache | 11.0% | 36.5921 |
| Synthetic | Water heavy sensitivity | 12.6% | 72.1704 |
| DU outdoor | Uniform cache | 17.6% | 54.9359 |
| DU outdoor | Water heavy sensitivity | 17.0% | 107.0176 |

## Charts

![V2.1 cache activity](../assets/v2_1/v2_1_cache_activity.pdf)
![V2.1 paired performance](../assets/v2_1/v2_1_paired_performance.pdf)
![V2.1 hit rate by environment](../assets/v2_1/v2_1_hit_rate_environment.pdf)
![V2.1 energy overhead](../assets/v2_1/v2_1_energy_overhead.pdf)

## Decision and limitations

The first full matrix supports retaining one cache slot. A second slot and adaptive prior are deferred because most loaded parcels returned unused, while the water heavy sensitivity increased energy overhead. The item prior is a sensitivity assumption, not a field-calibrated probability. The matrix uses bounded planner settings recorded in the manifest and does not claim unrestricted optimality.

## Evidence files

* Raw metrics: `Simulation/results/pgbm_v2_1_cache_experiments/raw_metrics/`
* Decision traces: `Simulation/results/pgbm_v2_1_cache_experiments/decision_traces/`
* Manifest: `Simulation/results/pgbm_v2_1_cache_experiments/manifests/pgbm_v2_1_cache_manifest_bounded_workers8.json`
* Summary: `Simulation/results/pgbm_v2_1_cache_experiments/summary/`
