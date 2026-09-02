# range-web-1 local app images

`manifest.yaml` references a few `range/*:local` images that are baked by the
range image-build step (out of band, into the range's registry) before the
manifest is applied. Each is a minimal, deliberately-vulnerable target — a
facade with exactly the one weakness its scenario needs, no live payloads:

| Image                        | Scenario            | Weakness (target only) |
|------------------------------|---------------------|------------------------|
| `range/go-pprof:local`       | go-pprof            | exposes `/debug/pprof` |
| `range/exposed-git:local`    | exposed-git         | nginx serving a checked-in `.git/` holding a **fake** AWS key |
| `range/laravel-debug:local`  | laravel-debug       | `APP_DEBUG=true`, dumps a **fake** app key on error |
| `range/path-traversal:local` | umbraco-lfo / wp-lfi| `MODE=umbraco`/`wordpress` path-traversal reflector |
| `range/sql-error:local`      | sql-error           | reflects a raw SQL error on `?id=` |
| `range/dom-xss:local`        | dom-xss             | `innerHTML` sink on `location.hash` |

The remaining apps use public pinned images
(`ghcr.io/christophetd/log4shell-vulnerable-app`, `mongo-express:0.54.0`,
`httpd:2.4.48`, `vulhub/spring-cloud-gateway:3.1.0`).

These images run **only inside the isolated range**.
