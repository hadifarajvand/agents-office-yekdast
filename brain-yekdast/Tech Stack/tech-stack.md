# Tech stack for client builds

- Default build target: JavaScript/TypeScript web apps.
- Builds run inside a throwaway, hardened container with no direct internet; packages come through the office's egress proxy.
- Previews are deployed to the owner's Dokploy server (AlmaLinux 9.7 VPS) into a separate "previews" project, behind authentication by default.

Record real stack decisions for each client here as short notes (one decision per note).
