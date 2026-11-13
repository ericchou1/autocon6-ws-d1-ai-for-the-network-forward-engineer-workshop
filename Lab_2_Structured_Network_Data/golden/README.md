# Golden captures

Real output captured from the workshop topology (SR Linux 25.10.2, containerlab) on 2026-11-08. Nothing here is typed in or trimmed.

| File | What it is |
|---|---|
| `r1_bgp.txt`, `r2_bgp.txt`, `r3_bgp.txt` | `show network-instance default protocols bgp neighbor`, all sessions established |
| `r1_bgp_degraded.txt` | Same command on r1 while r3's neighbor was removed — the eBGP session sits in `active` |
| `r3_bgp_empty.txt` | Same command on r3 with no neighbors configured. **Zero bytes** — SR Linux prints nothing at all in that case. Real edge case, keep it. |
| `expected.json` | Hand-verified ground truth for the five files above. This is the eval's answer key. |
| `r1_ospf.txt`, `r2_ospf.txt` | `show network-instance default protocols ospf neighbor` (used by a Lab 3 stretch goal) |
| `r?_routing.cfg` | `info flat from running` for interfaces, routing-policy and the default network-instance only — the parts that matter, ~40 lines each |
| `r3_routing_degraded.cfg` | `r3_routing.cfg` with the eBGP neighbor line missing — the planted inconsistency for the cross-device exercise |
| `r?_running.cfg` | The *full* `info flat from running`, ~680 lines each, mostly ACL and system defaults — used to make a point about context windows |
