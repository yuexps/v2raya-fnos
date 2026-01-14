# v2rayA for fnOS

This is a v2rayA application packaged for fnOS.

## About v2rayA

v2rayA is a V2Ray client that supports global transparent proxy and provides a web-based management interface.

## Access

After installation, access the web interface via the fnOS desktop icon.

## Version Info

- v2rayA Version: 2.2.7.4
- v2ray-core Version: 5.41.0
- xray-core Version: Latest (auto-updated)
- Architecture: x86_64

## Core Selection

This application includes both v2ray-core and xray-core. You can choose which one to use:

### During Installation
The installation wizard will prompt you to select your preferred proxy core:
- **v2ray-core** (default) - Stable and recommended for most users
- **xray-core** - Feature-rich implementation with support for XTLS and more protocols

### After Installation
You can change the core selection at any time through the application settings:
1. Open the Settings page
2. Select "Core Selection"
3. Choose your preferred proxy core
4. Restart the application to apply the change

### Manual Configuration (Advanced)
You can also manually set the `CORE_TYPE` environment variable before starting the application:
```bash
# Use v2ray-core (default)
export CORE_TYPE=v2ray

# Use xray-core
export CORE_TYPE=xray
```

For detailed configuration information, see [CORE_CONFIG_GUIDE.md](CORE_CONFIG_GUIDE.md).

## Resources

- [FNOS](https://developer.fnnas.com/docs/guide)
- [v2rayA](https://github.com/v2rayA/v2rayA)
- [v2ray-core](https://github.com/v2fly/v2ray-core)
- [xray-core](https://github.com/XTLS/Xray-core)
