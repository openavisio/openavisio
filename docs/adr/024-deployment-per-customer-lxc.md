# ADR 024: One Deployment per customer, isolated in its own LXC

**Status:** Accepted

## Context

OpenAvisio is sold as a hosted service. Two ways to serve multiple customers: build multi-tenancy into the software (shared database, tenant separation in code), or run a fully separate Deployment per customer.

## Decision

One complete Deployment per customer (frontend, backend, aiservice, database), each in its own LXC container on Proxmox, reachable under its own sub- or customer domain. No multi-tenancy in the application code. ("Deployment" is the canonical term — see CONTEXT.md.)

## Consequences

**Good:**
- Hard data isolation between customers — no tenant-leak bug class, a strong argument for medical data ("Daten bleiben beim Betreiber")
- The software stays identical for hosted customers and self-hosters — one codebase, no tenant branching
- Per-customer upgrades, backups, and resource limits

**Trade-offs:**
- Operations scale linearly with customers (updates, monitoring, backups per LXC) — needs automation as the customer count grows
- No cross-Deployment features (central admin, aggregated stats) without extra tooling
- Higher base resource cost per customer than shared tenancy
