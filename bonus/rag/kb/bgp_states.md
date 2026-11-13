# BGP Session States

The BGP finite state machine defines six states a session can be in. Understanding which state means what is the foundation of BGP troubleshooting.

## Idle

The starting state. No resources allocated, no TCP connection attempted. A session sitting in Idle is unusual outside of initial bring-up — it usually indicates the BGP process is disabled, the neighbor isn't configured, or an error has reset the session.

## Connect

The local router is attempting TCP/179 to the peer. If TCP succeeds, transition to OpenSent. If TCP fails (RST, timeout, ICMP unreachable), transition to Active. Sessions usually pass through Connect quickly — if they linger here, the underlying IP path is the suspect.

## Active

TCP connection attempts have failed. The session is retrying. **A peer stuck in Active is almost always a configuration problem on the *other* side**: peer not configured, peer firewalled, peer-AS mismatch on the peer side, ACL blocking TCP/179. The state name is misleading — "Active" sounds healthy but it means "actively failing."

## OpenSent

TCP is established; the local side has sent its OPEN message. Waiting for the peer's OPEN. If the peer's OPEN contains an AS number that doesn't match what we expect, the session resets.

## OpenConfirm

The peer's OPEN was accepted (AS numbers match, capabilities compatible). Waiting for the first KEEPALIVE message to confirm the session.

## Established

The session is fully up. UPDATE messages can flow. Routes get exchanged according to import/export policies.

## Healthy progression

In a healthy network, sessions should reach Established within a few seconds of configuration and stay there. Idle and Active are the diagnostic states — the names describe local-side behavior, but the cause is usually peer-side.
