# PGBM Initial Solution V2: task replacement recourse findings

## V2-এর core feature

V2 হলো formulation-aligned one-for-one active-mission task replacement recourse। নতুন task আসলে সব responder UAV active থাকলে প্রতিটি active mission-এর uncompleted task একবার করে replace করার candidate পরীক্ষা করা হয়। Completed task এবং completed route prefix অপরিবর্তিত থাকে। নতুন task-এর item demand current onboard inventory দিয়ে মেটানো সম্ভব হতে হয়; remaining route existing collision-aware 3D routing layer দিয়ে একই base-এ ফেরত তৈরি হয়; এবং শুধু positive `ΔJ = J_new - J_old` হলে সর্বোচ্চ gain-এর candidate গ্রহণ করা হয়। Displaced task waiting queue-তে ফিরে যায়।

V2-তে reserve inventory, base reload, multiple-task replacement, full fleet reoptimization বা future task information ব্যবহার করা হয়নি। এগুলো Version 3 scope। V1-এর entry point এবং evidence অপরিবর্তিত রাখা হয়েছে।

## Experiment-এর সংক্ষিপ্ত চিত্র

| বিষয় | ব্যবহৃত configuration |
|---|---|
| Environment | Synthetic এবং DU outdoor |
| Operation window | ১২০ মিনিট |
| Arrival phase | ০–৪০ high, ৪০–৮০ medium, ৮০–১২০ low |
| Task load | ৩০, ৬০, ৯০ |
| UAV count | ৩, ৫, ৮, ১০ |
| Seed | ১০১–১১০ |
| Configuration | ২৪০টি; প্রতি configuration-এ V1 এবং V2 paired row |
| Evidence | ৪৮০ metrics row এবং ২৪০ V2 decision trace |

V1-এর preserved canonical matrix থেকে comparison row নেওয়া হয়েছে। V2 একই local scene এবং task seed protocol-এ চালানো হয়েছে। In-memory paired validation-এ recourse disabled করলে V2 fixed control-এর objective, served task, distance, energy এবং candidate count V1-এর সঙ্গে মিলে গেছে।

## V2 algorithm কীভাবে assignment এবং recourse ঠিক করে

V2-এর initial dispatch V1-এর bounded brute-force assignment এবং task-order rule ব্যবহার করে। নতুন task arrival হলে V2 পুরো fleet replan করে না। Current mission state থেকে প্রতিটি active UAV এবং প্রতিটি uncompleted task-এর জন্য একটি candidate তৈরি হয়।

1. Current time-এ UAV-এর position, completed task, remaining task, onboard item, payload এবং consumed energy project করা হয়।
2. একটি uncompleted task সরিয়ে নতুন task-টি একই mission position-এ বসানো হয়।
3. যদি service ইতিমধ্যে চলতে থাকে, সেই service interrupt করা হয় না; candidate current service শেষ হওয়ার পরের suffix পরিবর্তন করে।
4. New task এবং remaining mission-এর item demand current onboard inventory দিয়ে মেটানো যায় কি না পরীক্ষা করা হয়।
5. Current position থেকে revised task sequence এবং একই physical base পর্যন্ত collision-aware 3D route তৈরি হয়।
6. Payload, route, energy reserve এবং ১২০ মিনিটের horizon feasibility পরীক্ষা হয়।
7. Old remaining mission value এবং revised remaining mission value হিসাব করে `ΔJ` বের করা হয়।
8. সব candidate-এর মধ্যে সর্বোচ্চ positive `ΔJ` গ্রহণ করা হয়; positive candidate না থাকলে নতুন task queue-তে থাকে।

এখানে final episode objective প্রত্যেক completed task-এর service value একবার গণনা করে। Replanning-এর সময়ের intermediate objective যোগ করে double counting করা হয়নি।

## Simulation environment এবং route flow

V2 একই V1 scene, task, parcel, drop-off waypoint, payload, energy এবং route contracts ব্যবহার করে। প্রতিটি task individual delivery request; task-এর food, water এবং medical demand, ২–৪ m vertical drop-off waypoint এবং ০.৫ মিনিট per parcel service duration অপরিবর্তিত আছে।

একটি active mission-এর route হলো Base → task waypoint sequence → Base। Recourse trigger হলে completed route অংশকে আবার plan করা হয় না। UAV-এর projected current position থেকে শুধু remaining suffix নতুন করে route করা হয়। প্রতিটি leg existing cruise-altitude check, direct line check, blocked হলে grid A* এবং vertical clearance check অনুসরণ করে।

## Result বোঝার জন্য প্রধান metric

* `Objective`: completion-time exponential service value; বেশি মানে priority-weighted assistance value বেশি।
* `Served task` এবং `Dropped parcel`: task এবং parcel আলাদা unit; parcel rate item delivery pressure দেখায়।
* `Deferred`: horizon শেষে complete না হওয়া task।
* `Accepted replacement`: positive `ΔJ` সহ গৃহীত task replacement।
* `Replacement gain`: accepted replacement-গুলোর `ΔJ` যোগফল; এটি episode objective নয়, event-level recourse evidence।
* `Runtime`, `Planner`, `Route`, `Recourse`: computation কোথায় সময় নিচ্ছে তা আলাদা করে দেখায়।

## Environment-level V1 বনাম V2 ফলাফল

| Environment | Algorithm | Objective | Served | Task rate | Parcel rate | Deferred | Delay min | Runtime s | Accepted replacement |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | V1 | 10.43 ± 4.22 | 20.12 ± 7.95 | 33.5\% | 36.6\% | 39.88 ± 24.05 | 31.64 ± 4.05 | 20.225 | 0.00 ± 0.00 |
| DU outdoor | V2 | 11.70 ± 4.53 | 19.63 ± 7.63 | 32.7\% | 33.4\% | 40.37 ± 23.82 | 23.21 ± 3.97 | 59.408 | 10.19 ± 5.22 |
| Synthetic | V1 | 23.48 ± 9.36 | 40.40 ± 16.73 | 67.3\% | 69.1\% | 19.60 ± 19.34 | 18.30 ± 4.54 | 3.733 | 0.00 ± 0.00 |
| Synthetic | V2 | 23.84 ± 9.34 | 39.36 ± 16.19 | 65.6\% | 66.9\% | 20.64 ± 19.75 | 16.08 ± 3.33 | 10.355 | 8.57 ± 5.98 |

এই table থেকে কয়েকটি ফলাফল পরিষ্কার। DU outdoor-এ V2 objective 10.43 থেকে 11.70 হয়েছে (প্রায় 12.2% বৃদ্ধি), যদিও served task 20.12 থেকে 19.63 এবং parcel rate 36.6% থেকে 33.4%-এ সামান্য কমেছে। Synthetic-এ objective 23.48 থেকে 23.84 (প্রায় 1.5%) বেড়েছে, কিন্তু served task এবং parcel rate-ও সামান্য কমেছে। অর্থাৎ V2-এর লাভ raw task count নয়; active mission-এর মধ্যে কোন task আগে complete করলে time-sensitive service value বেশি হবে, সেটি বেছে নেওয়া।
সবচেয়ে গুরুত্বপূর্ণ পরিবর্তনটি Delay min-এ। DU outdoor-এ average delay 31.64 থেকে 23.21 মিনিটে (8.43 মিনিট বা প্রায় 26.6%) এবং Synthetic-এ 18.30 থেকে 16.08 মিনিটে (2.22 মিনিট বা প্রায় 12.1%) কমেছে। Delay min হলো task detect হওয়ার সময় থেকে delivery complete হওয়া পর্যন্ত গড় সময়। নতুন task এলে V2 শুধু সেই replacement নেয় যার revised remaining mission value পুরনো mission-এর চেয়ে বেশি; ফলে অপেক্ষমাণ high-value task অনেক ক্ষেত্রে আগের completion position পায়। তবে এটি সব task-এর delay কমেছে—এমন দাবি নয়; কিছু lower-value displaced task queue-তে ফেরত যায়, তাই served count কমেও average completed-task delay কমতে পারে।
এর বিপরীতে V2 runtime DU outdoor-এ 20.225 থেকে 59.408 s এবং Synthetic-এ 3.733 থেকে 10.355 s হয়েছে। কারণ প্রতিটি recourse trigger-এ সম্ভাব্য active UAV ও displaced task-এর জন্য feasibility এবং revised route পরীক্ষা করা হয়। তাই V2-এর মূল trade-off হলো—priority-weighted service value এবং completion delay উন্নত করার বিনিময়ে অতিরিক্ত computation।

## Task load পরিবর্তনের প্রভাব

| Environment | Tasks | V1 objective | V2 objective | Δ objective | V1 task rate | V2 task rate | V1 parcel rate | V2 parcel rate | V2 accepted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | 30 | 8.26 | 8.82 | 0.56 | 56.5% | 55.0% | 52.5% | 49.3% | 5.25 |
| DU outdoor | 60 | 11.32 | 12.50 | 1.18 | 36.7% | 35.2% | 34.8% | 30.7% | 10.78 |
| DU outdoor | 90 | 11.73 | 13.79 | 2.07 | 23.8% | 23.6% | 22.6% | 20.3% | 14.55 |
| Synthetic | 30 | 14.99 | 15.17 | 0.17 | 87.3% | 86.7% | 85.8% | 84.6% | 2.73 |
| Synthetic | 60 | 25.01 | 25.42 | 0.40 | 72.5% | 70.7% | 69.4% | 66.7% | 8.72 |
| Synthetic | 90 | 30.43 | 30.93 | 0.50 | 57.2% | 55.2% | 52.2% | 49.4% | 14.25 |

Task load বাড়লে queue pressure বাড়ে এবং V1 ও V2 দুই version-এর service rate সাধারণত কমে। V2-এর expected value হলো arrival চলাকালীন high-value task এলে existing mission-এর lower-value uncompleted task-এর জায়গায় সেটিকে আনা; তাই improvement সবচেয়ে অর্থপূর্ণ হবে সেই configuration-এ যেখানে active mission এবং নতুন task overlap বেশি।

## UAV সংখ্যা পরিবর্তনের প্রভাব

| Environment | UAV | V1 objective | V2 objective | Δ objective | V1 served | V2 served | V1 runtime s | V2 runtime s | V2 accepted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | 3 | 5.77 | 6.97 | 1.20 | 10.83 | 10.83 | 13.331 | 51.276 | 7.93 |
| DU outdoor | 5 | 8.92 | 10.27 | 1.35 | 17.10 | 16.70 | 17.240 | 52.861 | 10.03 |
| DU outdoor | 8 | 12.53 | 13.82 | 1.29 | 24.23 | 23.47 | 23.273 | 67.167 | 11.70 |
| DU outdoor | 10 | 14.52 | 15.75 | 1.23 | 28.33 | 27.53 | 27.058 | 66.327 | 11.10 |
| Synthetic | 3 | 15.14 | 15.79 | 0.65 | 25.23 | 24.33 | 2.726 | 8.065 | 9.50 |
| Synthetic | 5 | 21.42 | 21.92 | 0.50 | 36.30 | 35.27 | 3.453 | 9.696 | 10.07 |
| Synthetic | 8 | 27.41 | 27.69 | 0.27 | 47.70 | 46.63 | 4.351 | 12.531 | 8.30 |
| Synthetic | 10 | 29.94 | 29.95 | 0.01 | 52.37 | 51.20 | 4.403 | 11.127 | 6.40 |

UAV সংখ্যা বাড়ালে available capacity বাড়ে, ফলে recourse trigger-এর সুযোগ কমতেও পারে, কারণ নতুন task queue-তে না থেকে idle UAV-তে dispatch হতে পারে। এই কারণে V2 accepted replacement সবসময় fleet size-এর সঙ্গে monotonic হবে না। V2-এর meaningful comparison হলো একই fleet size-এ V1-এর তুলনায় objective, delay, served task এবং parcel delivery কীভাবে বদলেছে।

## সম্পূর্ণ task load এবং fleet matrix

নিচের matrix-এ দশটি seed-এর average দেওয়া হয়েছে। `ΔObj` হলো V2 objective minus V1 objective, `ΔServed` হলো served task-এর পার্থক্য, এবং `ΔParcel` হলো parcel delivery rate-এর percentage-point difference।

| Environment | Task | UAV | V1 Obj | V2 Obj | ΔObj | V1 Served | V2 Served | ΔServed | V1 Parcel | V2 Parcel | ΔParcel | V2 Repl | V2 Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | 30 | 3 | 5.11 | 5.92 | 0.81 | 10.50 | 10.20 | -0.30 | 30.9% | 26.9% | -4.0 pp | 6.10 | 37.612 |
| DU outdoor | 30 | 5 | 7.47 | 8.32 | 0.85 | 15.90 | 15.40 | -0.50 | 48.1% | 43.7% | -4.4 pp | 7.00 | 42.588 |
| DU outdoor | 30 | 8 | 9.87 | 10.23 | 0.35 | 20.20 | 19.60 | -0.60 | 63.8% | 61.4% | -2.4 pp | 4.70 | 38.111 |
| DU outdoor | 30 | 10 | 10.59 | 10.80 | 0.22 | 21.20 | 20.80 | -0.40 | 67.2% | 65.2% | -2.0 pp | 3.20 | 28.559 |
| DU outdoor | 60 | 3 | 5.95 | 7.42 | 1.48 | 10.80 | 11.40 | 0.60 | 16.5% | 14.4% | -2.2 pp | 8.00 | 50.711 |
| DU outdoor | 60 | 5 | 9.49 | 10.70 | 1.21 | 17.80 | 17.20 | -0.60 | 27.6% | 23.4% | -4.3 pp | 9.10 | 54.161 |
| DU outdoor | 60 | 8 | 13.63 | 14.77 | 1.14 | 26.90 | 25.30 | -1.60 | 42.4% | 37.8% | -4.6 pp | 13.00 | 50.260 |
| DU outdoor | 60 | 10 | 16.20 | 17.10 | 0.90 | 32.60 | 30.70 | -1.90 | 52.5% | 47.4% | -5.1 pp | 13.00 | 36.383 |
| DU outdoor | 90 | 3 | 6.26 | 7.55 | 1.30 | 11.20 | 10.90 | -0.30 | 11.2% | 9.4% | -1.9 pp | 9.70 | 65.505 |
| DU outdoor | 90 | 5 | 9.80 | 11.80 | 1.99 | 17.60 | 17.50 | -0.10 | 18.3% | 15.9% | -2.5 pp | 14.00 | 61.833 |
| DU outdoor | 90 | 8 | 14.08 | 16.47 | 2.39 | 25.60 | 25.50 | -0.10 | 27.3% | 24.6% | -2.7 pp | 17.40 | 113.128 |
| DU outdoor | 90 | 10 | 16.76 | 19.35 | 2.59 | 31.20 | 31.10 | -0.10 | 33.5% | 31.2% | -2.2 pp | 17.10 | 134.039 |
| Synthetic | 30 | 3 | 11.98 | 12.63 | 0.65 | 22.60 | 22.00 | -0.60 | 71.1% | 67.5% | -3.7 pp | 6.40 | 4.040 |
| Synthetic | 30 | 5 | 15.30 | 15.32 | 0.01 | 27.20 | 27.00 | -0.20 | 90.1% | 89.0% | -1.2 pp | 3.70 | 3.222 |
| Synthetic | 30 | 8 | 16.26 | 16.28 | 0.02 | 27.50 | 27.50 | 0.00 | 90.9% | 90.9% | +0.0 pp | 0.80 | 3.355 |
| Synthetic | 30 | 10 | 16.44 | 16.44 | 0.00 | 27.50 | 27.50 | 0.00 | 90.9% | 90.9% | +0.0 pp | 0.00 | 3.612 |
| Synthetic | 60 | 3 | 15.65 | 16.40 | 0.76 | 25.40 | 24.70 | -0.70 | 37.3% | 34.6% | -2.6 pp | 8.80 | 11.164 |
| Synthetic | 60 | 5 | 22.84 | 23.71 | 0.87 | 39.90 | 38.60 | -1.30 | 60.9% | 57.8% | -3.1 pp | 11.00 | 14.512 |
| Synthetic | 60 | 8 | 29.70 | 29.78 | 0.08 | 53.30 | 51.90 | -1.40 | 87.6% | 84.6% | -3.0 pp | 9.70 | 17.878 |
| Synthetic | 60 | 10 | 31.86 | 31.77 | -0.09 | 55.30 | 54.50 | -0.80 | 91.6% | 89.6% | -2.0 pp | 5.40 | 11.775 |
| Synthetic | 90 | 3 | 17.81 | 18.34 | 0.54 | 27.70 | 26.30 | -1.40 | 25.2% | 22.8% | -2.3 pp | 13.30 | 8.992 |
| Synthetic | 90 | 5 | 26.11 | 26.73 | 0.62 | 41.80 | 40.20 | -1.60 | 40.3% | 38.0% | -2.3 pp | 15.50 | 11.353 |
| Synthetic | 90 | 8 | 36.28 | 37.00 | 0.72 | 62.30 | 60.50 | -1.80 | 64.2% | 61.2% | -3.1 pp | 14.40 | 16.359 |
| Synthetic | 90 | 10 | 41.52 | 41.65 | 0.12 | 74.30 | 71.60 | -2.70 | 79.2% | 75.6% | -3.6 pp | 13.80 | 17.993 |

এই matrix-এর প্রধান patternগুলো হলো: (১) DU outdoor-এর ১২টি configuration-এর সবকটিতেই V2 objective V1-এর চেয়ে বেশি। বিশেষ করে ৯০ task-এ gain 1.30 থেকে 2.59 পর্যন্ত, অর্থাৎ load বাড়লে recourse-এর priority benefit বেশি দৃশ্যমান হয়। (২) DU outdoor-এ ৬০ task/৩ UAV ছাড়া served task সামান্য কমেছে বা প্রায় অপরিবর্তিত থেকেছে; parcel rate-ও সব cell-এ কমেছে। কারণ V2 কিছু lower-value active task সরিয়ে বেশি time-sensitive task বসায়—এটি throughput-maximization rule নয়। (৩) Synthetic-এ low load এবং বেশি UAV থাকলে V1-এর capacity প্রায় যথেষ্ট; ৩০ task/১০ UAV-এ accepted replacement গড় ০ এবং objective পরিবর্তন ০.০০। তাই সেখানে V2-এর বাড়তি লাভ সীমিত। (৪) Synthetic-এর ৬০ task/১০ UAV cell-এ একমাত্র সামান্য negative objective change (-0.09) দেখা গেছে—এই configuration-এ replacement-এর লাভ computation/queue trade-off পুরোপুরি offset করতে পারেনি। (৫) ৯০ task-এ accepted replacement এবং runtime সাধারণত বাড়ে; DU outdoor-এ ৯০ task/১০ UAV runtime 134.039 s পর্যন্ত উঠেছে।
সুতরাং matrix দেখায় যে V2-এর value সবচেয়ে বেশি congestion বা active-mission overlap থাকা configuration-এ। UAV বাড়ালে service capacity বাড়ে, কিন্তু নতুন task idle UAV-তে সরাসরি dispatch হলে replacement দরকার কমে; তাই accepted replacement fleet size-এর সঙ্গে সবসময় monotonic হয় না।

## Recourse decision এবং rejection evidence

V2 decision trace-এ প্রতিটি trigger-এর জন্য candidate UAV, displaced task, item feasibility, route feasibility, energy feasibility, old value, new value, gain এবং final decision রাখা হয়েছে। নিচের table-এ trigger-level rejection reason দেওয়া হলো; candidate-level কারণ সম্পূর্ণ JSON trace-এ দেখা যাবে।

| Trigger-level rejection reason | Evidence count |
|---|---:|
| no_positive_gain | 2113 |
| no_feasible_candidate | 1842 |
| no_uncompleted_active_task | 433 |

এই অংশটির সহজ অর্থ হলো: নতুন task আসার সময় যদি UAV-গুলো active থাকে, V2 দেখে কোনো চলমান mission-এর একটি uncompleted task সরিয়ে নতুন task বসালে সত্যিই লাভ হবে কি না। একটি trigger-এ একাধিক candidate পরীক্ষা হতে পারে; তাই table-এর সংখ্যা candidate count নয়, trigger-level final outcome। মোট ৬৬৩৯টি trigger-এর মধ্যে ২২৫১টি replacement গৃহীত এবং ৪৩৮৮টি গৃহীত হয়নি—অর্থাৎ acceptance rate প্রায় 33.9%।
`no_positive_gain` (2113) সবচেয়ে বেশি দেখা গেছে। অর্থাৎ candidate route ও item-এর দিক থেকে সম্ভব হলেও পুরনো task সরিয়ে নতুন task বসালে remaining service value বাড়েনি; তাই বর্তমান mission অপরিবর্তিত রাখা হয়েছে। `no_feasible_candidate` (1842) মানে কোনো candidate-ই item/inventory, route, energy reserve, return বা horizon-এর সব শর্ত একসঙ্গে পূরণ করতে পারেনি। `no_uncompleted_active_task` (433) মানে active mission-এ সরানোর মতো uncompleted task ছিল না। এই rejection-এ নতুন task হারিয়ে যায় না—pending queue-তে থেকে পরবর্তী dispatch-এর জন্য অপেক্ষা করে। Candidate-level কারণগুলো JSON decision trace-এ আলাদা করে রাখা হয়েছে।

## Runtime এবং bottleneck

V2 runtime-কে তিনটি অংশে পড়া হয়েছে: initial dispatch planner time, dispatch route evaluation time এবং recourse candidate evaluation time। V2-এর recourse runtime আলাদা রাখা হয়েছে, যাতে নতুন feature-এর computational overhead V1-এর route search-এর সঙ্গে মিশে না যায়।

| Environment | Algorithm | Runtime s | Planner s | Route s | Recourse s | Candidate | Search truncated | Safe return |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | V1 | 20.225 | 20.223 | 19.566 | 0.000 | 249477 | 4.1 | 100.0% |
| DU outdoor | V2 | 59.408 | 46.568 | 44.692 | 12.784 | 288639 | 4.8 | 100.0% |
| Synthetic | V1 | 3.733 | 3.731 | 3.561 | 0.000 | 65211 | 1.0 | 100.0% |
| Synthetic | V2 | 10.355 | 8.961 | 8.513 | 1.326 | 57343 | 0.8 | 100.0% |

এখানে Runtime s বলতে simulation program-এর computation time বোঝায়; এটি UAV-এর real flight time বা task delay নয়। Planner s হলো initial assignment search-এর সময়, Route s হলো collision-aware route তৈরি/মূল্যায়নের সময়, আর Recourse s হলো V2-তে নতুন task replacement candidate পরীক্ষা করার অতিরিক্ত সময়।
Table-এর প্রধান bottleneck হলো route evaluation। V1-এ DU outdoor-এর 20.225 s runtime-এর মধ্যে route অংশ 19.566 s (প্রায় 96.7%); Synthetic-এ 3.561 s (প্রায় 95.4%)। তবে V2-এর Runtime, Planner, Route এবং Recourse timer-গুলো mutually exclusive নয়। Planner-এর মধ্যে route evaluation থাকতে পারে এবং recourse candidate যাচাইয়ের সময়ও route check চলে; তাই এগুলো সরাসরি যোগ করে total runtime ধরা যাবে না। উদাহরণ হিসেবে DU outdoor V2-তে Route 44.692 s + Recourse 12.784 s = 57.476 s, যেখানে total Runtime 59.408 s; বাকি 1.932 s event handling, dispatch bookkeeping এবং অন্যান্য overhead। Synthetic-এ 8.513 + 1.326 = 9.839 s, total 10.355 s; residual 0.516 s। অর্থাৎ breakdown-টি bottleneck বোঝার diagnostic view, additive accounting নয়। এই ফল দেখায় V2-এর বাড়তি computation-এর বড় অংশ repeated route feasibility পরীক্ষা, আর underlying route search-ই এখনও প্রধান cost centre।
DU outdoor Synthetic-এর তুলনায় অনেক ধীর, কারণ DU-তে polygon obstacle geometry এবং blocked হলে grid A* path search বেশি কাজ করে। V2 runtime V1-এর তুলনায় DU-তে প্রায় 2.94 গুণ এবং Synthetic-এ প্রায় 2.77 গুণ হয়েছে। Safe return 100% মানে simulation-এর feasibility filter পেরিয়ে সব executed mission base-এ ফিরেছে; এটি field-flight reliability-এর প্রমাণ নয়। `Search truncated` হলো যেসব dispatch ৫০,০০০ candidate limit-এ পৌঁছেছে তার গড় সংখ্যা, আর Candidate হলো পরীক্ষিত candidate plan-এর গড় count। তাই পরবর্তী efficiency কাজের প্রধান দিক হবে route reuse/cache hit measurement, early feasibility pruning এবং scalable candidate search।

## Energy model এবং energy ফলাফল

V1 এবং V2 উভয় version-এ energy একটি configured accounting model দিয়ে গণনা করা হয়েছে। কোনো travel segment-এর জন্য `d` হলো route distance, `m` হলো বহন করা payload mass এবং `a+` হলো positive ascent distance।

```text
E_travel = d * e_distance + d * m * e_payload + a+ * e_ascent
E_service = service_time * e_service
E_mission = sum(E_travel) + sum(E_service)
```

এই run-এ `e_distance = 1.0 J/m`, `e_payload = 0.05 J/(kg m)`, `e_ascent = 0.20 J/m` এবং `e_service = 0.50 J/min`। প্রতিটি initial বা recourse candidate-এর জন্য UAV-এর ইতিমধ্যে ব্যবহৃত energy-এর সঙ্গে revised route-এর additional energy যোগ করে check করা হয়: `energy_consumed + additional_energy + reserve_energy <= energy_capacity`। এখানে capacity 1000 J এবং reserve 200 J; তাই projected remaining energy-এর অন্তত reserve অংশ mission শেষে অবশিষ্ট থাকতে হয়।

`Total energy` হলো পুরো episode-এ সম্পন্ন বা horizon পর্যন্ত চলা সব mission-এর cumulative energy। এটি কোনো একক UAV-এর একবারের battery state নয়। প্রতিটি UAV base-এ ফিরে resupply/turnaround শেষ করলে পরের mission-এ নতুন full capacity থেকে শুরু করে; V1/V2-তে battery degradation বা mission-to-mission persistent battery depletion model করা হয়নি।

| Environment | Algorithm | Total energy (J) | Energy/served task (J) | Energy/dropped parcel (J) | Distance (m) | Travel time (min) |
|---|---|---:|---:|---:|---:|---:|
| DU outdoor | V1 | 6142.4 ± 2417.8 | 310.2 ± 62.2 | 199.3 ± 38.8 | 5928.2 ± 2335.5 | 592.8 ± 233.5 |
| DU outdoor | V2 | 6078.6 ± 2385.3 | 314.7 ± 69.0 | 224.5 ± 61.3 | 5854.1 ± 2300.6 | 585.4 ± 230.1 |
| Synthetic | V1 | 5319.7 ± 2101.8 | 134.4 ± 28.4 | 84.3 ± 17.9 | 5041.4 ± 1988.8 | 504.1 ± 198.9 |
| Synthetic | V2 | 5368.8 ± 2123.8 | 138.9 ± 27.6 | 88.5 ± 17.0 | 5083.6 ± 2006.9 | 508.4 ± 200.7 |

Energy result-এর মূল trade-off হলো: DU outdoor-এ V2 total energy 6142.4 J থেকে 6078.6 J-এ এবং distance 5928.2 m থেকে 5854.1 m-এ কমেছে, কারণ V2 কিছু lower-value task replace/queue করে এবং infeasible বা energy-expensive candidate গ্রহণ করে না। কিন্তু completed task ও parcel কম হওয়ায় প্রতি served task energy 310.2 থেকে 314.7 J এবং প্রতি dropped parcel 199.3 থেকে 224.5 J হয়েছে। Synthetic-এ V2 total energy 5319.7 J থেকে 5368.8 J এবং distance 5041.4 m থেকে 5083.6 m-এ সামান্য বেড়েছে; accepted recourse-এর revised route এই অতিরিক্ত movement তৈরি করেছে। তাই শুধু total energy দিয়ে efficiency বিচার করা যাবে না; cumulative energy, energy per completed service এবং distance একসঙ্গে দেখতে হবে।

## Expanded V1 বনাম V2 result matrix

নিচের দুইটি matrix-এ প্রতিটি cell-এর ১০টি seed-এর mean ± standard deviation দেওয়া হয়েছে। ফলে objective, served task, parcel volume, queue, energy, recourse এবং runtime-এর seed variability একই সঙ্গে দেখা যায়।

### Service, parcel এবং queue metrics

| Environment | Task | UAV | Alg | Objective | Served | Task rate | Req. parcel | Dropped parcel | Deferred | Delay min | Peak queue |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | 30 | 3 | V1 | 5.11 ± 1.50 | 10.50 ± 3.10 | 35.0% ± 10.3% | 48.8 ± 3.9 | 14.9 ± 2.2 | 19.50 ± 3.10 | 34.33 ± 3.96 | 19.5 ± 3.1 |
| DU outdoor | 30 | 3 | V2 | 5.92 ± 1.24 | 10.20 ± 2.82 | 34.0% ± 9.4% | 48.8 ± 3.9 | 13.0 ± 3.8 | 19.80 ± 2.82 | 24.28 ± 7.21 | 19.8 ± 2.8 |
| DU outdoor | 30 | 5 | V1 | 7.47 ± 1.42 | 15.90 ± 3.31 | 53.0% ± 11.0% | 48.8 ± 3.9 | 23.3 ± 4.4 | 14.10 ± 3.31 | 33.31 ± 5.01 | 14.3 ± 3.3 |
| DU outdoor | 30 | 5 | V2 | 8.32 ± 1.35 | 15.40 ± 3.13 | 51.3% ± 10.4% | 48.8 ± 3.9 | 21.1 ± 4.7 | 14.60 ± 3.13 | 26.05 ± 4.38 | 14.8 ± 3.2 |
| DU outdoor | 30 | 8 | V1 | 9.87 ± 1.57 | 20.20 ± 3.12 | 67.3% ± 10.4% | 48.8 ± 3.9 | 31.0 ± 6.1 | 9.80 ± 3.12 | 28.36 ± 3.05 | 10.2 ± 3.0 |
| DU outdoor | 30 | 8 | V2 | 10.23 ± 1.68 | 19.60 ± 3.63 | 65.3% ± 12.1% | 48.8 ± 3.9 | 29.8 ± 7.4 | 10.40 ± 3.63 | 25.66 ± 2.68 | 10.7 ± 3.5 |
| DU outdoor | 30 | 10 | V1 | 10.59 ± 1.46 | 21.20 ± 2.74 | 70.7% ± 9.1% | 48.8 ± 3.9 | 32.8 ± 6.5 | 8.80 ± 2.74 | 25.97 ± 3.18 | 9.2 ± 2.4 |
| DU outdoor | 30 | 10 | V2 | 10.80 ± 1.45 | 20.80 ± 2.86 | 69.3% ± 9.5% | 48.8 ± 3.9 | 31.8 ± 7.1 | 9.20 ± 2.86 | 24.88 ± 2.78 | 9.5 ± 2.6 |
| DU outdoor | 60 | 3 | V1 | 5.95 ± 1.27 | 10.80 ± 1.62 | 18.0% ± 2.7% | 101.3 ± 5.1 | 16.7 ± 1.5 | 49.20 ± 1.62 | 33.64 ± 3.56 | 49.2 ± 1.6 |
| DU outdoor | 60 | 3 | V2 | 7.42 ± 1.11 | 11.40 ± 1.71 | 19.0% ± 2.9% | 101.3 ± 5.1 | 14.5 ± 2.1 | 48.60 ± 1.71 | 21.94 ± 3.70 | 48.6 ± 1.7 |
| DU outdoor | 60 | 5 | V1 | 9.49 ± 1.52 | 17.80 ± 1.99 | 29.7% ± 3.3% | 101.3 ± 5.1 | 27.9 ± 2.1 | 42.20 ± 1.99 | 33.21 ± 4.06 | 42.2 ± 2.0 |
| DU outdoor | 60 | 5 | V2 | 10.70 ± 1.55 | 17.20 ± 2.49 | 28.7% ± 4.1% | 101.3 ± 5.1 | 23.6 ± 3.2 | 42.80 ± 2.49 | 23.16 ± 1.62 | 42.8 ± 2.5 |
| DU outdoor | 60 | 8 | V1 | 13.63 ± 2.00 | 26.90 ± 3.03 | 44.8% ± 5.1% | 101.3 ± 5.1 | 42.9 ± 3.7 | 33.10 ± 3.03 | 32.95 ± 3.25 | 33.1 ± 3.0 |
| DU outdoor | 60 | 8 | V2 | 14.77 ± 2.18 | 25.30 ± 3.47 | 42.2% ± 5.8% | 101.3 ± 5.1 | 38.2 ± 5.5 | 34.70 ± 3.47 | 23.79 ± 1.95 | 34.7 ± 3.5 |
| DU outdoor | 60 | 10 | V1 | 16.20 ± 2.62 | 32.60 ± 4.99 | 54.3% ± 8.3% | 101.3 ± 5.1 | 53.0 ± 6.6 | 27.40 ± 4.99 | 32.62 ± 2.58 | 27.4 ± 5.0 |
| DU outdoor | 60 | 10 | V2 | 17.10 ± 3.07 | 30.70 ± 5.25 | 51.2% ± 8.8% | 101.3 ± 5.1 | 47.8 ± 7.8 | 29.30 ± 5.25 | 25.73 ± 2.90 | 29.3 ± 5.3 |
| DU outdoor | 90 | 3 | V1 | 6.26 ± 1.25 | 11.20 ± 1.69 | 12.4% ± 1.9% | 151.2 ± 8.3 | 16.9 ± 2.3 | 78.80 ± 1.69 | 33.00 ± 3.00 | 78.8 ± 1.7 |
| DU outdoor | 90 | 3 | V2 | 7.55 ± 1.47 | 10.90 ± 1.97 | 12.1% ± 2.2% | 151.2 ± 8.3 | 14.1 ± 3.0 | 79.10 ± 1.97 | 20.23 ± 2.53 | 79.1 ± 2.0 |
| DU outdoor | 90 | 5 | V1 | 9.80 ± 2.03 | 17.60 ± 2.88 | 19.6% ± 3.2% | 151.2 ± 8.3 | 27.6 ± 4.3 | 72.40 ± 2.88 | 31.72 ± 2.92 | 72.4 ± 2.9 |
| DU outdoor | 90 | 5 | V2 | 11.80 ± 2.02 | 17.50 ± 2.46 | 19.4% ± 2.7% | 151.2 ± 8.3 | 23.9 ± 2.8 | 72.50 ± 2.46 | 19.99 ± 3.83 | 72.5 ± 2.5 |
| DU outdoor | 90 | 8 | V1 | 14.08 ± 2.42 | 25.60 ± 3.50 | 28.4% ± 3.9% | 151.2 ± 8.3 | 41.1 ± 5.5 | 64.40 ± 3.50 | 30.10 ± 2.84 | 64.4 ± 3.5 |
| DU outdoor | 90 | 8 | V2 | 16.47 ± 2.44 | 25.50 ± 3.14 | 28.3% ± 3.5% | 151.2 ± 8.3 | 37.1 ± 4.6 | 64.50 ± 3.14 | 20.81 ± 2.48 | 64.5 ± 3.1 |
| DU outdoor | 90 | 10 | V1 | 16.76 ± 2.80 | 31.20 ± 4.24 | 34.7% ± 4.7% | 151.2 ± 8.3 | 50.4 ± 6.7 | 58.80 ± 4.24 | 30.52 ± 3.05 | 58.8 ± 4.2 |
| DU outdoor | 90 | 10 | V2 | 19.35 ± 2.56 | 31.10 ± 3.81 | 34.6% ± 4.2% | 151.2 ± 8.3 | 47.0 ± 4.4 | 58.90 ± 3.81 | 21.94 ± 2.85 | 58.9 ± 3.8 |
| Synthetic | 30 | 3 | V1 | 11.98 ± 1.48 | 22.60 ± 1.78 | 75.3% ± 5.9% | 48.6 ± 3.6 | 34.5 ± 3.1 | 7.40 ± 1.78 | 23.66 ± 2.74 | 9.7 ± 1.3 |
| Synthetic | 30 | 3 | V2 | 12.63 ± 1.29 | 22.00 ± 1.89 | 73.3% ± 6.3% | 48.6 ± 3.6 | 32.7 ± 3.9 | 8.00 ± 1.89 | 20.22 ± 3.86 | 10.4 ± 1.2 |
| Synthetic | 30 | 5 | V1 | 15.30 ± 1.10 | 27.20 ± 1.40 | 90.7% ± 4.7% | 48.6 ± 3.6 | 43.8 ± 4.1 | 2.80 ± 1.40 | 16.15 ± 1.85 | 5.5 ± 1.4 |
| Synthetic | 30 | 5 | V2 | 15.32 ± 0.99 | 27.00 ± 1.56 | 90.0% ± 5.2% | 48.6 ± 3.6 | 43.2 ± 4.0 | 3.00 ± 1.56 | 16.66 ± 2.04 | 5.6 ± 1.3 |
| Synthetic | 30 | 8 | V1 | 16.26 ± 1.14 | 27.50 ± 1.43 | 91.7% ± 4.8% | 48.6 ± 3.6 | 44.2 ± 4.1 | 2.50 ± 1.43 | 11.41 ± 1.10 | 3.4 ± 1.1 |
| Synthetic | 30 | 8 | V2 | 16.28 ± 1.11 | 27.50 ± 1.43 | 91.7% ± 4.8% | 48.6 ± 3.6 | 44.2 ± 4.1 | 2.50 ± 1.43 | 11.38 ± 1.07 | 3.4 ± 1.1 |
| Synthetic | 30 | 10 | V1 | 16.44 ± 1.12 | 27.50 ± 1.43 | 91.7% ± 4.8% | 48.6 ± 3.6 | 44.2 ± 4.1 | 2.50 ± 1.43 | 10.37 ± 0.86 | 2.7 ± 1.3 |
| Synthetic | 30 | 10 | V2 | 16.44 ± 1.12 | 27.50 ± 1.43 | 91.7% ± 4.8% | 48.6 ± 3.6 | 44.2 ± 4.1 | 2.50 ± 1.43 | 10.37 ± 0.86 | 2.7 ± 1.3 |
| Synthetic | 60 | 3 | V1 | 15.65 ± 1.86 | 25.40 ± 2.46 | 42.3% ± 4.1% | 105.1 ± 6.7 | 39.1 ± 2.7 | 34.60 ± 2.46 | 21.60 ± 2.34 | 35.0 ± 2.2 |
| Synthetic | 60 | 3 | V2 | 16.40 ± 1.62 | 24.70 ± 2.83 | 41.2% ± 4.7% | 105.1 ± 6.7 | 36.2 ± 2.6 | 35.30 ± 2.83 | 16.31 ± 1.43 | 35.7 ± 2.6 |
| Synthetic | 60 | 5 | V1 | 22.84 ± 2.17 | 39.90 ± 3.84 | 66.5% ± 6.4% | 105.1 ± 6.7 | 63.9 ± 5.2 | 20.10 ± 3.84 | 21.64 ± 2.43 | 22.0 ± 2.7 |
| Synthetic | 60 | 5 | V2 | 23.71 ± 1.69 | 38.60 ± 3.63 | 64.3% ± 6.0% | 105.1 ± 6.7 | 60.7 ± 5.2 | 21.40 ± 3.63 | 18.03 ± 2.39 | 23.2 ± 2.8 |
| Synthetic | 60 | 8 | V1 | 29.70 ± 2.66 | 53.30 ± 3.20 | 88.8% ± 5.3% | 105.1 ± 6.7 | 92.0 ± 7.2 | 6.70 ± 3.20 | 18.93 ± 3.11 | 11.0 ± 2.4 |
| Synthetic | 60 | 8 | V2 | 29.78 ± 2.25 | 51.90 ± 3.90 | 86.5% ± 6.5% | 105.1 ± 6.7 | 88.7 ± 8.4 | 8.10 ± 3.90 | 18.63 ± 1.55 | 11.9 ± 2.6 |
| Synthetic | 60 | 10 | V1 | 31.86 ± 1.72 | 55.30 ± 1.77 | 92.2% ± 2.9% | 105.1 ± 6.7 | 96.3 ± 7.7 | 4.70 ± 1.77 | 15.01 ± 2.54 | 8.7 ± 2.2 |
| Synthetic | 60 | 10 | V2 | 31.77 ± 1.88 | 54.50 ± 2.59 | 90.8% ± 4.3% | 105.1 ± 6.7 | 94.2 ± 8.7 | 5.50 ± 2.59 | 15.17 ± 1.97 | 8.4 ± 2.4 |
| Synthetic | 90 | 3 | V1 | 17.81 ± 1.59 | 27.70 ± 2.41 | 30.8% ± 2.7% | 156.4 ± 5.5 | 39.3 ± 3.1 | 62.30 ± 2.41 | 20.89 ± 2.28 | 62.3 ± 2.4 |
| Synthetic | 90 | 3 | V2 | 18.34 ± 2.04 | 26.30 ± 3.09 | 29.2% ± 3.4% | 156.4 ± 5.5 | 35.7 ± 4.6 | 63.70 ± 3.09 | 14.87 ± 0.74 | 63.7 ± 3.1 |
| Synthetic | 90 | 5 | V1 | 26.11 ± 2.29 | 41.80 ± 3.82 | 46.4% ± 4.2% | 156.4 ± 5.5 | 63.0 ± 5.2 | 48.20 ± 3.82 | 20.04 ± 2.16 | 48.5 ± 3.8 |
| Synthetic | 90 | 5 | V2 | 26.73 ± 2.88 | 40.20 ± 4.44 | 44.7% ± 4.9% | 156.4 ± 5.5 | 59.4 ± 5.7 | 49.80 ± 4.44 | 15.95 ± 2.12 | 50.0 ± 4.3 |
| Synthetic | 90 | 8 | V1 | 36.28 ± 2.87 | 62.30 ± 5.50 | 69.2% ± 6.1% | 156.4 ± 5.5 | 100.4 ± 9.3 | 27.70 ± 5.50 | 19.91 ± 1.98 | 29.3 ± 4.6 |
| Synthetic | 90 | 8 | V2 | 37.00 ± 3.19 | 60.50 ± 5.38 | 67.2% ± 6.0% | 156.4 ± 5.5 | 95.6 ± 8.8 | 29.50 ± 5.38 | 17.08 ± 1.53 | 30.4 ± 5.0 |
| Synthetic | 90 | 10 | V1 | 41.52 ± 2.75 | 74.30 ± 4.22 | 82.6% ± 4.7% | 156.4 ± 5.5 | 123.8 ± 8.0 | 15.70 ± 4.22 | 19.96 ± 2.31 | 19.6 ± 3.9 |
| Synthetic | 90 | 10 | V2 | 41.65 ± 2.94 | 71.60 ± 5.10 | 79.6% ± 5.7% | 156.4 ± 5.5 | 118.1 ± 9.1 | 18.40 ± 5.10 | 18.33 ± 1.87 | 21.4 ± 4.6 |

### Resource এবং recourse metrics

| Environment | Task | UAV | Alg | Distance m | Travel min | Energy J | Energy/served | Energy/parcel | Safe return | Trigger | Accepted | Rejected | Gain | Runtime s |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DU outdoor | 30 | 3 | V1 | 2832.4 ± 219.5 | 283.2 ± 21.9 | 2934.2 ± 224.0 | 299.0 ± 81.1 | 201.2 ± 37.0 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 11.485 ± 6.489 |
| DU outdoor | 30 | 3 | V2 | 2787.2 ± 184.9 | 278.7 ± 18.5 | 2887.1 ± 191.5 | 308.9 ± 113.1 | 254.2 ± 128.4 | 100.0% ± 0.0% | 20.2 ± 2.7 | 6.1 ± 2.4 | 14.1 ± 1.5 | 1.302 ± 0.573 | 37.612 ± 26.444 |
| DU outdoor | 30 | 5 | V1 | 4602.5 ± 327.9 | 460.3 ± 32.8 | 4762.7 ± 330.5 | 315.1 ± 87.1 | 213.3 ± 55.3 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 13.509 ± 7.659 |
| DU outdoor | 30 | 5 | V2 | 4542.6 ± 271.2 | 454.3 ± 27.1 | 4722.1 ± 290.6 | 319.9 ± 77.4 | 239.7 ± 82.0 | 100.0% ± 0.0% | 15.2 ± 2.6 | 7.0 ± 1.9 | 8.2 ± 2.8 | 1.409 ± 0.380 | 42.588 ± 22.340 |
| DU outdoor | 30 | 8 | V1 | 6495.0 ± 350.3 | 649.5 ± 35.0 | 6709.3 ± 357.3 | 342.0 ± 73.6 | 225.6 ± 55.4 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 15.143 ± 8.093 |
| DU outdoor | 30 | 8 | V2 | 6516.3 ± 384.0 | 651.6 ± 38.4 | 6748.6 ± 404.1 | 358.3 ± 85.7 | 245.7 ± 90.0 | 100.0% ± 0.0% | 6.9 ± 3.1 | 4.7 ± 1.7 | 2.2 ± 2.1 | 0.903 ± 0.461 | 38.111 ± 19.065 |
| DU outdoor | 30 | 10 | V1 | 7404.9 ± 529.3 | 740.5 ± 52.9 | 7635.4 ± 542.9 | 367.6 ± 70.1 | 241.2 ± 53.2 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 14.422 ± 7.936 |
| DU outdoor | 30 | 10 | V2 | 7380.9 ± 625.2 | 738.1 ± 62.5 | 7624.9 ± 647.6 | 373.6 ± 65.9 | 251.0 ± 64.7 | 100.0% ± 0.0% | 5.1 ± 3.1 | 3.2 ± 1.3 | 1.9 ± 2.3 | 0.676 ± 0.347 | 28.559 ± 12.537 |
| DU outdoor | 60 | 3 | V1 | 2942.4 ± 162.8 | 294.2 ± 16.3 | 3058.2 ± 165.8 | 290.4 ± 54.4 | 184.9 ± 23.1 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 12.684 ± 6.289 |
| DU outdoor | 60 | 3 | V2 | 2929.5 ± 250.8 | 292.9 ± 25.1 | 3057.3 ± 252.9 | 276.1 ± 62.3 | 216.6 ± 47.4 | 100.0% ± 0.0% | 43.8 ± 4.4 | 8.0 ± 1.9 | 35.8 ± 4.8 | 1.350 ± 0.429 | 50.711 ± 34.337 |
| DU outdoor | 60 | 5 | V1 | 4751.1 ± 265.1 | 475.1 ± 26.5 | 4939.5 ± 270.9 | 281.6 ± 43.5 | 178.3 ± 20.8 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 18.059 ± 7.983 |
| DU outdoor | 60 | 5 | V2 | 4782.8 ± 273.1 | 478.3 ± 27.3 | 4981.2 ± 271.4 | 297.6 ± 63.5 | 215.0 ± 34.8 | 100.0% ± 0.0% | 36.0 ± 4.9 | 9.1 ± 1.9 | 26.9 ± 5.2 | 1.660 ± 0.435 | 54.161 ± 25.153 |
| DU outdoor | 60 | 8 | V1 | 7604.1 ± 342.3 | 760.4 ± 34.2 | 7897.7 ± 357.3 | 297.5 ± 40.9 | 185.3 ± 17.5 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 23.971 ± 10.611 |
| DU outdoor | 60 | 8 | V2 | 7373.2 ± 323.8 | 737.3 ± 32.4 | 7667.6 ± 331.0 | 309.0 ± 49.5 | 204.8 ± 32.6 | 100.0% ± 0.0% | 30.3 ± 5.5 | 13.0 ± 2.3 | 17.3 ± 4.7 | 2.283 ± 0.365 | 50.260 ± 25.969 |
| DU outdoor | 60 | 10 | V1 | 9321.8 ± 522.4 | 932.2 ± 52.2 | 9681.0 ± 538.8 | 303.4 ± 49.8 | 184.9 ± 21.9 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 30.386 ± 14.888 |
| DU outdoor | 60 | 10 | V2 | 9162.9 ± 461.7 | 916.3 ± 46.2 | 9526.9 ± 492.9 | 318.7 ± 55.3 | 204.0 ± 32.9 | 100.0% ± 0.0% | 26.8 ± 4.8 | 13.0 ± 2.1 | 13.8 ± 3.9 | 2.599 ± 0.624 | 36.383 ± 17.980 |
| DU outdoor | 90 | 3 | V1 | 3038.9 ± 122.2 | 303.9 ± 12.2 | 3153.7 ± 123.5 | 287.2 ± 43.1 | 189.7 ± 25.4 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 15.823 ± 9.331 |
| DU outdoor | 90 | 3 | V2 | 2883.3 ± 189.1 | 288.3 ± 18.9 | 2998.0 ± 192.0 | 284.4 ± 61.1 | 221.7 ± 50.5 | 100.0% ± 0.0% | 66.9 ± 5.1 | 9.7 ± 3.1 | 57.2 ± 5.9 | 1.369 ± 0.524 | 65.505 ± 38.326 |
| DU outdoor | 90 | 5 | V1 | 4960.8 ± 186.1 | 496.1 ± 18.6 | 5141.6 ± 183.6 | 300.1 ± 55.8 | 190.9 ± 33.9 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 20.151 ± 8.642 |
| DU outdoor | 90 | 5 | V2 | 4918.5 ± 233.8 | 491.8 ± 23.4 | 5110.3 ± 218.9 | 298.0 ± 49.2 | 216.9 ± 30.3 | 100.0% ± 0.0% | 59.6 ± 4.9 | 14.0 ± 5.1 | 45.6 ± 8.6 | 2.157 ± 0.889 | 61.833 ± 25.722 |
| DU outdoor | 90 | 8 | V1 | 7667.8 ± 377.4 | 766.8 ± 37.7 | 7941.7 ± 381.3 | 316.3 ± 51.7 | 196.8 ± 30.8 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 30.704 ± 12.132 |
| DU outdoor | 90 | 8 | V2 | 7709.9 ± 290.4 | 771.0 ± 29.0 | 8005.1 ± 298.4 | 318.2 ± 39.7 | 218.4 ± 24.8 | 100.0% ± 0.0% | 48.8 ± 3.9 | 17.4 ± 4.1 | 31.4 ± 6.0 | 2.923 ± 0.867 | 113.128 ± 49.163 |
| DU outdoor | 90 | 10 | V1 | 9516.9 ± 390.9 | 951.7 ± 39.1 | 9854.2 ± 393.7 | 321.9 ± 50.1 | 198.8 ± 28.2 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 36.365 ± 8.356 |
| DU outdoor | 90 | 10 | V2 | 9262.3 ± 497.4 | 926.2 ± 49.7 | 9614.5 ± 492.4 | 313.8 ± 44.5 | 206.2 ± 21.1 | 100.0% ± 0.0% | 40.5 ± 6.3 | 17.1 ± 2.7 | 23.4 ± 6.4 | 3.208 ± 0.810 | 134.039 ± 47.750 |
| Synthetic | 30 | 3 | V1 | 2521.9 ± 135.6 | 252.2 ± 13.6 | 2671.2 ± 135.9 | 118.7 ± 8.8 | 78.0 ± 7.9 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 2.069 ± 1.400 |
| Synthetic | 30 | 3 | V2 | 2607.0 ± 131.7 | 260.7 ± 13.2 | 2765.2 ± 132.2 | 126.4 ± 10.7 | 85.7 ± 10.9 | 100.0% ± 0.0% | 16.9 ± 2.2 | 6.4 ± 2.0 | 10.5 ± 3.0 | 1.627 ± 0.672 | 4.040 ± 2.335 |
| Synthetic | 30 | 5 | V1 | 3801.4 ± 301.6 | 380.1 ± 30.2 | 4001.2 ± 310.4 | 147.3 ± 12.1 | 92.2 ± 12.0 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 1.118 ± 0.569 |
| Synthetic | 30 | 5 | V2 | 3863.4 ± 277.9 | 386.3 ± 27.8 | 4071.7 ± 286.8 | 151.0 ± 10.4 | 94.9 ± 10.5 | 100.0% ± 0.0% | 8.0 ± 3.1 | 3.7 ± 1.3 | 4.3 ± 2.7 | 0.876 ± 0.444 | 3.222 ± 1.809 |
| Synthetic | 30 | 8 | V1 | 4766.2 ± 471.5 | 476.6 ± 47.1 | 4980.5 ± 484.6 | 181.3 ± 17.5 | 113.7 ± 16.2 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 1.102 ± 0.597 |
| Synthetic | 30 | 8 | V2 | 4786.7 ± 479.4 | 478.7 ± 47.9 | 5002.2 ± 492.8 | 182.1 ± 17.7 | 114.2 ± 16.3 | 100.0% ± 0.0% | 1.4 ± 1.0 | 0.8 ± 1.0 | 0.6 ± 0.7 | 0.159 ± 0.281 | 3.355 ± 1.723 |
| Synthetic | 30 | 10 | V1 | 4992.2 ± 538.4 | 499.2 ± 53.8 | 5209.9 ± 552.0 | 189.7 ± 20.1 | 119.0 ± 17.8 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 1.078 ± 0.540 |
| Synthetic | 30 | 10 | V2 | 4992.2 ± 538.4 | 499.2 ± 53.8 | 5209.9 ± 552.0 | 189.7 ± 20.1 | 119.0 ± 17.8 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 3.612 ± 1.897 |
| Synthetic | 60 | 3 | V1 | 2685.7 ± 81.4 | 268.6 ± 8.1 | 2842.1 ± 83.0 | 112.8 ± 10.5 | 73.0 ± 6.2 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 2.862 ± 1.195 |
| Synthetic | 60 | 3 | V2 | 2706.9 ± 72.6 | 270.7 ± 7.3 | 2866.8 ± 78.6 | 117.9 ± 17.5 | 79.6 ± 7.1 | 100.0% ± 0.0% | 34.3 ± 4.6 | 8.8 ± 3.1 | 25.5 ± 3.6 | 1.532 ± 0.637 | 11.164 ± 4.674 |
| Synthetic | 60 | 5 | V1 | 4406.2 ± 135.9 | 440.6 ± 13.6 | 4666.6 ± 140.4 | 118.0 ± 12.2 | 73.4 ± 5.7 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 4.039 ± 1.683 |
| Synthetic | 60 | 5 | V2 | 4444.6 ± 128.9 | 444.5 ± 12.9 | 4708.6 ± 140.9 | 123.0 ± 12.6 | 78.0 ± 5.3 | 100.0% ± 0.0% | 25.1 ± 5.7 | 11.0 ± 2.9 | 14.1 ± 3.9 | 2.320 ± 0.935 | 14.512 ± 4.221 |
| Synthetic | 60 | 8 | V1 | 6587.8 ± 374.3 | 658.8 ± 37.4 | 6966.9 ± 394.9 | 131.2 ± 12.0 | 76.2 ± 7.5 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 4.663 ± 3.470 |
| Synthetic | 60 | 8 | V2 | 6670.9 ± 238.7 | 667.1 ± 23.9 | 7065.6 ± 255.6 | 137.1 ± 15.0 | 80.5 ± 9.8 | 100.0% ± 0.0% | 14.8 ± 5.7 | 9.7 ± 3.3 | 5.1 ± 3.3 | 2.466 ± 1.039 | 17.878 ± 7.983 |
| Synthetic | 60 | 10 | V1 | 7628.7 ± 491.4 | 762.9 ± 49.1 | 8037.7 ± 523.9 | 145.5 ± 11.0 | 83.8 ± 7.3 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 3.644 ± 2.618 |
| Synthetic | 60 | 10 | V2 | 7647.2 ± 525.5 | 764.7 ± 52.5 | 8073.4 ± 561.6 | 148.5 ± 13.7 | 86.3 ± 9.1 | 100.0% ± 0.0% | 8.5 ± 4.6 | 5.4 ± 3.0 | 3.1 ± 3.0 | 1.472 ± 0.938 | 11.775 ± 5.478 |
| Synthetic | 90 | 3 | V1 | 2778.2 ± 70.1 | 277.8 ± 7.0 | 2943.9 ± 67.6 | 107.1 ± 10.5 | 75.4 ± 7.0 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 3.246 ± 1.557 |
| Synthetic | 90 | 3 | V2 | 2737.4 ± 64.2 | 273.7 ± 6.4 | 2898.1 ± 66.4 | 111.7 ± 14.9 | 82.7 ± 13.5 | 100.0% ± 0.0% | 57.9 ± 4.6 | 13.3 ± 2.4 | 44.6 ± 4.9 | 1.906 ± 0.364 | 8.992 ± 4.750 |
| Synthetic | 90 | 5 | V1 | 4541.3 ± 129.3 | 454.1 ± 12.9 | 4804.2 ± 130.8 | 115.9 ± 12.1 | 76.8 ± 8.0 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 5.201 ± 3.266 |
| Synthetic | 90 | 5 | V2 | 4552.5 ± 130.1 | 455.2 ± 13.0 | 4824.7 ± 144.8 | 121.6 ± 15.9 | 82.1 ± 10.0 | 100.0% ± 0.0% | 44.1 ± 7.1 | 15.5 ± 4.2 | 28.6 ± 5.3 | 2.442 ± 0.854 | 11.353 ± 5.917 |
| Synthetic | 90 | 8 | V1 | 7056.7 ± 176.0 | 705.7 ± 17.6 | 7472.0 ± 182.3 | 120.7 ± 9.5 | 75.0 ± 6.6 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 7.286 ± 2.764 |
| Synthetic | 90 | 8 | V2 | 7171.5 ± 53.5 | 717.1 ± 5.4 | 7598.7 ± 57.4 | 126.6 ± 12.0 | 80.1 ± 8.1 | 100.0% ± 0.0% | 28.7 ± 6.4 | 14.4 ± 4.1 | 14.3 ± 4.1 | 2.787 ± 1.140 | 16.359 ± 9.764 |
| Synthetic | 90 | 10 | V1 | 8730.8 ± 238.3 | 873.1 ± 23.8 | 9240.4 ± 251.5 | 124.8 ± 8.5 | 75.0 ± 5.9 | 100.0% ± 0.0% | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.000 ± 0.000 | 8.488 ± 3.596 |
| Synthetic | 90 | 10 | V2 | 8823.4 ± 197.4 | 882.3 ± 19.7 | 9340.6 ± 217.6 | 131.0 ± 9.7 | 79.5 ± 6.2 | 100.0% ± 0.0% | 24.1 ± 10.2 | 13.8 ± 6.5 | 10.3 ± 4.7 | 3.236 ± 1.573 | 17.993 ± 7.594 |

এই expanded matrix-এ absolute requested/dropped parcel, task rate, deferred task এবং peak queue সরাসরি দেওয়া হয়েছে; parcel rate একা দেখে service volume অনুমান করতে হবে না। Resource table-এ distance এবং energy পাশাপাশি থাকায় route length বাড়ার সঙ্গে payload/ascent/service energy কীভাবে বদলেছে সেটিও দেখা যায়।

## Recourse evidence: environment, load, fleet এবং phase

Trigger-level মোট outcome-এর পাশাপাশি trace থেকে acceptance rate আলাদা করে হিসাব করা হয়েছে। Accepted gain-এর mean ± standard deviation এখানে accepted event-এর `delta_J`; episode-level `replacement_gain` তার থেকে আলাদা cumulative quantity।

| Group type | Group | Trigger | Accepted | Acceptance rate | Rejected | Accepted gain mean ± std |
|---|---|---:|---:|---:|---:|---:|
| Environment | DU outdoor | 4001 | 1223 | 30.6% | 2778 | 0.179 ± 0.132 |
| Environment | Synthetic | 2638 | 1028 | 39.0% | 1610 | 0.203 ± 0.150 |
| Task load | 30 | 737 | 319 | 43.3% | 418 | 0.218 ± 0.141 |
| Task load | 60 | 2196 | 780 | 35.5% | 1416 | 0.201 ± 0.146 |
| Task load | 90 | 3706 | 1152 | 31.1% | 2554 | 0.174 ± 0.136 |
| UAV count | 3 | 2400 | 523 | 21.8% | 1877 | 0.174 ± 0.134 |
| UAV count | 5 | 1880 | 603 | 32.1% | 1277 | 0.180 ± 0.133 |
| UAV count | 8 | 1309 | 600 | 45.8% | 709 | 0.192 ± 0.139 |
| UAV count | 10 | 1050 | 525 | 50.0% | 525 | 0.213 ± 0.155 |
| Arrival phase | High | 3728 | 1223 | 32.8% | 2505 | 0.173 ± 0.130 |
| Arrival phase | Medium | 2265 | 886 | 39.1% | 1379 | 0.201 ± 0.143 |
| Arrival phase | Low | 646 | 142 | 22.0% | 504 | 0.255 ± 0.191 |

### Candidate-level rejection breakdown

একটি trigger-এর ভিতরে একাধিক candidate থাকতে পারে। তাই নিচের count candidate-level; আগের rejection table-এর count trigger-level final reason।

| Candidate outcome/reason | Count | Share of candidate evaluations |
|---|---:|---:|
| Onboard inventory | 21828 | 62.6% |
| Payload capacity | 0 | 0.0% |
| Route infeasible | 5 | 0.0% |
| Energy reserve | 154 | 0.4% |
| Horizon | 851 | 2.4% |
| Service in progress | 1447 | 4.1% |
| Non-positive gain | 6021 | 17.3% |
| Feasible positive gain | 4584 | 13.1% |

Accepted replacement-এর পরে 2025টি unique displaced-task instance-এর মধ্যে 558টি (27.6%) horizon-এর মধ্যে পরে complete হয়েছে এবং 1467টি (72.4%) deferred থেকেছে। মোট accepted event ছিল 2251; এর মধ্যে 226টি repeated displacement event, তাই event count এবং unique task count আলাদা করে report করা হয়েছে।
Accepted trace example: `du_outdoor_tasks_30_uavs_3_seed_101`-এ t=7.78 min-এ uav_1 দ্বারা `task_6` task-কে সরিয়ে `task_10` task বসানো হয়েছে; old value 0.244, new value 0.633, gain +0.390।
Rejected trace example: `du_outdoor_tasks_30_uavs_3_seed_101`-এ t=15.10 min-এ `task_9` task-এর জন্য selected candidate-এর gain -0.076; candidate feasible হলেও gain positive নয়, তাই final reason `no_positive_gain` এবং task queue-তে রাখা হয়েছে।

## Validation evidence

একটি sentence-এর বদলে paired matrix এবং ছোট deterministic replay fixture-এর evidence নিচে দেওয়া হলো। Fixed-control fixture-এ V1 এবং V2 recourse-disabled একই scenario-তে চালানো হয়েছে; heavy matrix-এর ২৪০টি pair-এ scenario fingerprint match আলাদা করে যাচাই করা হয়েছে।

| Validation check | Evidence | Result |
|---|---|---|
| Same scenario fingerprint এবং task realization | 240টি paired cell-এর fingerprint match | PASS |
| Fixed-control objective | V1 5.453757; V2 fixed 5.453757 | PASS |
| Fixed-control served task | Same served-task ID set | PASS |
| Fixed-control distance and energy | Both values match within tolerance | PASS |
| Fixed-control candidate count | Same candidate count | PASS |
| Deterministic replay | Repeated V2 run produced identical events and decisions | PASS |
| Duplicate completion | Completed event IDs are unique | PASS |
| Objective double-counting | Reported 5.453757; direct final-completion sum 5.453757 | PASS |

Validation fixture: `synthetic, seed 5, 12 tasks, 3 UAV`। এটি report-এর reproducibility check; full result matrix-এর performance estimate নয়।

## V2 result-এর অর্থ এবং limitation

1. V2 প্রথমবার active mission-এর uncompleted suffix পরিবর্তন করে নতুন task-এর priority value বিবেচনা করেছে।
2. Accepted replacement-এ displaced task queue-তে ফিরে যায়; এটি task হারিয়ে ফেলা নয়।
3. V2 current onboard inventory ব্যবহার করে, তাই নতুন task-এর item demand feasible না হলে recourse গ্রহণ করে না।
4. Completed route prefix এবং completed delivery immutable রাখা হয়েছে।
5. V2 objective final completion event থেকে একবার গণনা করা হয়েছে; replanning snapshot যোগ করে inflated করা হয়নি।
6. Safe return rate planner-এর route এবং energy filter-এর ফল; এটি field flight reliability নয়।
7. Energy values এখনও configured coefficients-এর ফল, field-calibrated physical battery measurement নয়।
8. V2 one-for-one rule পূর্ণ mathematical optimizer বা full fleet rolling-horizon optimizer নয়।
9. Reserve inventory, base reload, multiple replacement এবং broader reassignment V3-এর জন্য রাখা হয়েছে।

## উপসংহার এবং পরবর্তী কাজ

V1 একটি fixed active-mission reference হিসেবে অপরিবর্তিত রাখা হয়েছে। V2 সেই reference-এর উপর formulation-এর সীমিত recourse rule যোগ করেছে: নতুন high-value task এলে feasible হলে একটি active mission-এর একটি uncompleted task replace করা যায়। Paired matrix V1 এবং V2-এর operational outcome এবং recourse overhead একসঙ্গে দেখাবে।

পরবর্তী version-এ reserve inventory এবং active inventory-aware reassignment যোগ করার আগে V2-এর accepted এবং rejected decision trace, service-value gain, runtime overhead এবং environment sensitivity বিশ্লেষণ করা হবে।

## Reproducibility artifacts

* `Simulation/results/pgbm_v2_recourse_experiments/raw_metrics/pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv`: V1 এবং V2-এর ৪৮০টি metrics row।
* `Simulation/results/pgbm_v2_recourse_experiments/decision_traces/pgbm_v2_decision_traces.jsonl`: প্রতি V2 episode-এর complete recourse trace।
* `Simulation/run_pgbm_v2_experiment_matrix.py`: paired matrix execution script।
* `Simulation/pgbm_sim/v2/`: V2 runtime state, recourse evaluator, event runner এবং paired experiment logic।
* `docs/specs/0007-pgbm-v2-task-replacement-recourse.md`: accepted formulation-aligned design specification।
