---
title: Connection Timeout Errors on API Gateway
tags: networking, gateway, timeout
---

## Symptom

Clients report `ETIMEDOUT` errors when calling the `/v1/orders` endpoint during
peak traffic hours (12:00-14:00 UTC). Requests hang for roughly 30 seconds before
failing. This started after the gateway was scaled from 4 to 2 replicas last week.

## Root Cause

The API gateway's connection pool to the upstream `orders-service` was sized for
4 replicas' worth of concurrent connections (200 per replica = 800 total). After
scaling down to 2 replicas, the same client load exhausted the pool, causing new
connections to queue until the 30-second timeout fired.

## Resolution

1. Increase `upstream.orders-service.max_connections` from 200 to 500 per replica
   in `gateway-config.yaml`.
2. Enable connection pool metrics (`gateway_pool_saturation_ratio`) so saturation
   is visible before it causes timeouts.
3. Add a horizontal pod autoscaler rule that scales the gateway on pool saturation,
   not just CPU.

See also [[database-connection-pool-exhaustion]] for a related root cause pattern.

## Verification

After deploying the config change, `gateway_pool_saturation_ratio` stayed below
0.6 during the next peak window and no `ETIMEDOUT` errors were reported for 72 hours.
