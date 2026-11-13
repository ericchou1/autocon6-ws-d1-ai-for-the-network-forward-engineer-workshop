# Lab Topology Reference

The AutoCon6 workshop uses a three-node SR Linux topology in containerlab.

## Routers

- **r1** — AS 65001. The "core" router. Has iBGP to r2 (via loopback 10.0.0.1 ↔ 10.0.0.2), eBGP to r3 (10.1.13.1 ↔ 10.1.13.2).
- **r2** — AS 65001. iBGP to r1 only.
- **r3** — AS 65002. eBGP to r1 only.

## Underlying transport

OSPF area 0 runs between r1 and r2 to provide reachability between their loopback interfaces. iBGP uses those loopbacks as session endpoints, so OSPF must be healthy for iBGP to be healthy.

r3 is a stub external AS — it has a single eBGP session to r1 and no IGP relationship.

## Expected BGP sessions when healthy

- **r1**: two neighbors — r2 (iBGP, AS 65001) and r3 (eBGP, AS 65002). Both should be Established.
- **r2**: one neighbor — r1 (iBGP, AS 65001). Should be Established.
- **r3**: one neighbor — r1 (eBGP, AS 65001). Should be Established.

## Known issues

After `containerlab deploy`, r3's BGP neighbor entry may be silently dropped during the startup-config push (SR Linux 25.10 bug). The workaround is to apply the missing neighbor line live via `enter candidate / set / commit now` — Lab 3 Step 5 documents this.
