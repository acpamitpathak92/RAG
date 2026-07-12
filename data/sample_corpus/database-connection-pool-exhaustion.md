---
title: Database Connection Pool Exhaustion
tags: database, postgres, pool
---

## Symptom

The `billing-service` starts throwing `TooManyConnectionsError` after a deploy,
even though traffic hasn't increased. New pods fail health checks and get killed
by Kubernetes, which triggers more restarts and makes the problem worse.

## Root Cause

Each `billing-service` pod opens its own Postgres connection pool sized at 20
connections. Postgres itself is configured with `max_connections = 100`. When the
deployment rolled out with `maxSurge: 50%`, up to 6 pods were briefly running at
once (6 x 20 = 120 connections), exceeding the Postgres limit.

## Resolution

1. Lower `maxSurge` to 25% for `billing-service` so at most 5 pods run concurrently
   during a rollout (5 x 20 = 100, right at the limit - also lower per-pod pool size).
2. Reduce per-pod pool size from 20 to 15 connections.
3. Put PgBouncer in front of Postgres in transaction-pooling mode so the effective
   connection ceiling is decoupled from `max_connections`.

Related: [[connection-timeout-errors]] describes a similar exhaustion pattern at
the API gateway layer rather than the database layer.

## Verification

Watched `pg_stat_activity` connection counts during the next three deploys; peak
concurrent connections stayed at 82, well under the 100 limit, with zero
`TooManyConnectionsError` occurrences.
