# Common BGP Issues and Diagnostic Patterns

## Stuck in Active

Symptom: session shows state "Active" for an extended period.

Cause: the local router can't establish TCP/179 to the peer.

Diagnostic checklist:
- Is the peer IP reachable? Ping from the local router. If ping fails, the underlying IGP is the problem, not BGP.
- Is the peer's BGP process listening? `telnet <peer> 179` from the local router should connect immediately. If it refuses or times out, BGP isn't running there or a firewall is blocking it.
- Is there a firewall in the path? ACLs that allow ICMP but drop TCP/179 are common.
- Is the peer configured with the *local* router's IP as a neighbor? eBGP is bidirectional configuration — both sides must list each other.

## Stuck in OpenSent

Symptom: session transitions out of Connect but stops at OpenSent.

Cause: TCP is up but OPEN negotiation is failing.

Common reasons:
- AS number mismatch: local config says peer is AS X, but the peer's OPEN advertises AS Y.
- Authentication mismatch: MD5 password configured on one side only, or different passwords on each side.
- Capability mismatch (rare with modern implementations).

## Established but no routes

Symptom: session shows Established. Route table is empty for routes that should come from this peer.

Cause: the session is up, but no routes are being installed.

Common reasons:
- Export policies on the *peer* side are dropping everything before sending.
- Nothing is being redistributed into BGP on the peer (no `network` statements, no redistribute config). Sessions exchange routes that BGP knows about — if nothing's in BGP, nothing gets sent.
- Import policies on the *local* side are dropping everything received.
- Next-hop reachability: for iBGP, the next-hop must be reachable via the IGP. If the IGP is broken, BGP routes get installed in the BGP RIB but never make it to the route table.

## Flapping sessions

Symptom: session repeatedly establishes and tears down.

Cause: instability in the underlying transport or BGP keepalive mechanism.

Common reasons:
- BFD timers too aggressive — BFD declares the peer dead before genuine packet loss has actually occurred.
- Underlying IGP instability: the loopback used for iBGP becomes intermittently unreachable.
- MTU mismatch on the path: large UPDATE messages get fragmented or dropped silently.
