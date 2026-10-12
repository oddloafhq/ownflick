# CasaOS / ZimaOS submission

This folder is a proposed app definition for the IceWhale app store. It is not
an approved listing. Copy its contents to `Apps/Spooly/` in that repository.

The default store mount exposes `/DATA/Media` read-only. This allows browsing
without giving Spooly permission to change existing media. Users must select
their library directory. Downloads and trash deletion need a writable mount.

Store-created data directories are commonly root-owned, so this definition
overrides the image's non-root default with `user: "0:0"`. It has no privileged
mode, host network, Docker socket or device mounts. A user can change UID:GID
after assigning permissions to `/DATA/AppData/$AppID`.

The upstream image continues to run as UID 1000 by default. See the ordinary
[Docker guide](../../docs/docker.md) for non-root deployment.

Validation: Compose parsing, app-store build validation and the upstream image
smoke test. Physical CasaOS/ZimaOS hardware testing has not been performed.
