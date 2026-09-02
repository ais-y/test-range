# AIS-Y Test Range

> **⚠ DELIBERATELY VULNERABLE — ISOLATED RANGE ONLY**
>
> This repository builds a deliberately-vulnerable target range used to measure
> the AIS-Y attack-surface scanner's recall. Every application here is pinned to
> a known-vulnerable version **on purpose**. The apps are **targets, not
> attackers** — nothing in this repo attacks anything, and there are no live
> exploit payloads.
>
> Deploy and run **only inside the isolated range VPC**. Never expose these
> hosts on a shared network, a corporate network, or the public internet
> outside the range's own controlled address space.
>
> **Security contact:** security@aisy.ai

## What this is

Three hosts, each presenting a bundle of scenarios the scanner must discover
and flag:

| Host          | Runtime          | Contents |
|---------------|------------------|----------|
| `range-web-1` | k3s              | Tier-1 exploitable apps (log4shell, mongo-express, Apache proxy, Spring Cloud Gateway, Go pprof, exposed `.git`, Laravel debug, path-traversal, SQL-error, DOM XSS) |
| `range-web-2` | docker-compose   | Fingerprint facades (Salesforce aura, AEM, Telerik, Shiro, MOVEit), tier-2 detectors (GraphQL introspection, badsecrets cookie, cache-poisoning reflector, 403-bypass, swagger, JS secret bundle, vhosts, IIS shape, default-cred admin), and the five cert-defect TLS terminators |
| `range-legacy`| docker-compose   | Real but empty ftp/mysql/postgres/redis, plus banner-only sockets on 22/23/445/3389 |

The **authoritative** list of every hostname, port, certificate defect, planted
(fake) secret, and expected nuclei template id is
[`groundtruth/catalogue.yaml`](groundtruth/catalogue.yaml). Everything else in
this repo must agree with it.

## Discovery channels

Every scenario carries a `discovery_channel`, mirroring
`modules/test-range/dns.tf`'s `local.range_hosts` map - the point is to
measure *how* the scanner finds hosts, not just whether it finds vulnerabilities:

- **`ct`** - the hostname gets its own publicly-trusted ACM cert
  (`modules/test-range/ct_certs.tf`), issued and logged to certificate-
  transparency logs. Discoverable the way a real subfinder/crt.sh-style CT
  sweep finds subdomains, independent of any wordlist.
- **`brute_force`** - a common dictionary label (`www`, `api`, `admin`, ...)
  with no individual cert. Only findable by an active subdomain/vhost
  brute-force stage.
- **`none`** - three unguessable control labels (`edge-7f3a2c`,
  `w2-internal-9x`, `unlisted-b41`, `tier: control` in the catalogue) with a
  plain A record and no cert. These are the discovery-ceiling control: they
  must **never** be discovered. If one turns up in the product, it's a leak
  or an over-broad wordlist, not a scanner win. (A few other scenarios also
  carry `discovery_channel: none` for a different reason - raw legacy
  services reached by IP/port, not by hostname - those are not controls and
  are excluded from the control check; see `tier: control` vs `tier: service`
  in the catalogue.)

`recall/report.py` reports discovery recall (was the asset found at all) per
`ct`/`brute_force` channel, separately from template-id recall/precision
(did the finding actually fire), plus the control check above.

## Layout

```
scenarios/
  range-web-1/manifest.yaml        k3s manifest (tier-1 apps + Traefik routes)
  range-web-1/build/               local vulnerable app images (see its README)
  range-web-2/docker-compose.yml   facades, tier-2 apps, cert terminators, SNI router
  range-web-2/sni-router.conf      stream ssl_preread router owning host 443
  range-web-2/facades/             fingerprint-only static sites (+ tls.conf)
  range-web-2/apps/                tier-2 detector apps
  range-web-2/tls/                 cert-defect nginx terminator configs
  range-legacy/docker-compose.yml  real empty services + banner sockets
  range-legacy/banner/             banner-only socket image
certs/generate.sh                  openssl: the five defective certs
groundtruth/catalogue.yaml         authoritative known-answer catalogue
groundtruth/generate.py            catalogue + Terraform outputs -> manifest.json
recall/report.py                   manifest.json vs product findings -> recall/precision
web/robots.txt                     disallow-all, for every web host
web/.well-known/security.txt       range security-contact template
```

## Deployment (host cloud-init)

The range hosts are provisioned by Terraform; each host's cloud-init pulls this
bundle and brings up its slice:

1. **Certificates** — `BASE_DOMAIN=<range domain> certs/generate.sh` writes the
   five defective certs to `certs/out/`.
2. **`range-web-1`** — substitute `__BASE_DOMAIN__` in
   `scenarios/range-web-1/manifest.yaml`, then
   `k3s kubectl apply -f manifest.yaml`.
3. **`range-web-2`** — `docker compose up -d` from `scenarios/range-web-2/`
   (after step 1, which its TLS backends mount). All nine TLS scenarios (the
   four fingerprint facades and the five cert-defect hosts) share the host's
   single port 443: the `sni-router` container owns 443 and, using an nginx
   `stream` block with `ssl_preread`, passes each TLS connection through by SNI
   hostname to the right backend — no re-termination, so each cert-defect host's
   intentionally-broken cert reaches the scanner unchanged. Those backends are
   internal-only (no host port); only the router publishes `443:443`.
4. **`range-legacy`** — `docker compose up -d` from `scenarios/range-legacy/`.
5. Copy `web/robots.txt` and `web/.well-known/security.txt` onto each web host.

## Ground truth & recall

```bash
uv sync
# after Terraform has produced VPC/EIP outputs:
uv run python groundtruth/generate.py --tf-output outputs.json   # -> manifest.json
# after the scanner has run against the range org:
AISY_ORG_ID=<range org id> AISY_TOKEN=<token> \
  uv run python recall/report.py --backend graphql
```

`recall/report.py` prints recall/precision and every miss by name. The range
organisation id is filled in **after** the org is created — see the
`RANGE_ORG_ID` TODO in that file.

## Safety rules

- Planted secrets are **clearly-fake canary strings** (e.g. `AKIAFAKECANARY…`,
  `sk-range-FAKECANARY-…`). They authenticate nothing.
- The legacy data services start **empty** with throwaway, range-only
  credentials.
- No component initiates a connection to anything outside the range.
