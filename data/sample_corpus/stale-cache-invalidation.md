---
title: Stale Product Prices Served From Cache
tags: caching, redis, pricing
---

## Symptom

Customers occasionally see outdated prices on the product page for up to 15
minutes after a price change is published in the admin panel, even though the
admin panel confirms the update succeeded immediately.

## Root Cause

The product-price cache in Redis uses a fixed 15-minute TTL and is never
explicitly invalidated on price update - the admin panel write path only writes
to Postgres, not to Redis. The cache simply serves stale data until the TTL
naturally expires.

## Resolution

1. Add a cache-invalidation call (`DEL price:{product_id}`) to the admin panel's
   price-update handler, executed in the same transaction as the Postgres write.
2. Reduce the fallback TTL from 15 minutes to 2 minutes as a safety net for any
   invalidation calls that fail silently.
3. Emit a `price_cache_invalidated` event so downstream services (search index,
   recommendation engine) can also refresh in near real time.

## Verification

Ran 50 manual price updates through the admin panel and confirmed the storefront
reflected each new price within 3 seconds, well under the old 15-minute window.
