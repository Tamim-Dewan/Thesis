## A. Response Scenario and Task Generation

Following a major earthquake, scan UAVs survey the affected region and
report potential survivor-assistance locations to a central command center.
Each accepted detection is represented as a supply-delivery task. For task
$i$, the command center maintains its service location $p_i$, an operational
urgency score $\sigma_i$, a detection confidence score $c_i$, the required
quantity $r_i^q(t)$ of each relief item type $q$, and a task-specific
completion deadline $D_i$.

The sensing and assessment process itself is not optimized in this work.
Instead, the formulation assumes that these task-level inputs have already
been produced by the perception and command-center assessment pipeline.
The feasibility of obtaining such information from UAV-based sensing and
remote assessment will be supported separately using prior disaster-response
literature.

A task is considered available for UAV assignment only while it remains
unserved, has sufficient detection confidence, and has not passed its
operational deadline. Let $\mathcal{A}(t)$ denote the set of tasks that are
eligible for assignment at decision time $t$. Conceptually,

$$
\mathcal{A}(t)
=
\left\{
i :
\text{task $i$ is pending},
\;
c_i \geq c_{\min},
\;
t < D_i
\right\}.
\tag{1}
$$

Thus, the optimization does not attempt to dispatch responder UAVs to every
reported location. It considers only sufficiently reliable and currently
actionable tasks.