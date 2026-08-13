

# v2rayA for fnOS

v2rayA application package for fnOS.

## Features

- **Unix Domain Socket**: Access via the fnOS Unified Gateway using Unix Domain Socket, avoiding extra TCP port exposure.
- **Multi-architecture**: Supports both x86_64 and arm64.
- **Built-in Core**: Includes pre-compiled v2raya_core, ready to use out of the box.
- **Automated Updates**: Weekly auto-builds and pre-release generation via GitHub Actions to keep the core and GeoIP databases current.

## Transparent Proxy Tip
If transparent proxy is required, it is recommended to use the tproxy mode for full compatibility with Docker containers, UDP, DNS and LAN traffic.

## Access

After installation, open the v2rayA WebUI via the fnOS desktop shortcut.

## Resources

- [fnOS Developer Guide](https://developer.fnnas.com/docs/guide)
- [v2rayA Repository](https://github.com/v2rayA/v2rayA)
