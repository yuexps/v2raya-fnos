import os
import sys

def patch_file(filepath, search_str, replace_str, check_str=None):
    if not os.path.exists(filepath):
        print(f"[ERROR] 文件不存在: {filepath}")
        return False
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if check_str and check_str in content:
        print(f"[INFO] 已经应用过补丁: {filepath}")
        return True
        
    if search_str not in content:
        print(f"[ERROR] 找不到锚点字符串: {filepath}")
        return False
        
    new_content = content.replace(search_str, replace_str, 1)
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
        
    print(f"[SUCCESS] 成功修补: {filepath}")
    return True

def main():
    print("开始自动适配新版 v2rayA 源码...")
    success = True

    # 1. 适配 conf/environmentConfig.go
    env_config_path = "v2rayA/service/conf/environmentConfig.go"
    env_search_1 = '\tAddress              string `id:"address" short:"a" default:"0.0.0.0:2017" desc:"Listening address"`'
    env_replace_1 = '\tAddress              string `id:"address" short:"a" default:"0.0.0.0:2017" desc:"Listening address"`\n\tSocket               string `id:"socket" desc:"Unix socket path for listening"`\n\tBaseUrl              string `id:"baseurl" default:"/" desc:"Base URL path prefix"`'
    
    env_search_2 = '''\terr := gonfig.Load(&params, gonfig.Conf{
		FileDisable:       true,
		FlagIgnoreUnknown: false,
		EnvPrefix:         "V2RAYA_",
	})
	if err != nil {
		if err.Error() != "unexpected word while parsing flags: '-test.v'" {
			log2.Fatal(err)
		}
	}
	if params.ShowVersion {'''
    
    env_replace_2 = '''\terr := gonfig.Load(&params, gonfig.Conf{
		FileDisable:       true,
		FlagIgnoreUnknown: false,
		EnvPrefix:         "V2RAYA_",
	})
	if err != nil {
		if err.Error() != "unexpected word while parsing flags: '-test.v'" {
			log2.Fatal(err)
		}
	}
	if params.BaseUrl == "" {
		params.BaseUrl = "/"
	} else {
		if !strings.HasPrefix(params.BaseUrl, "/") {
			params.BaseUrl = "/" + params.BaseUrl
		}
		if params.BaseUrl != "/" {
			params.BaseUrl = strings.TrimSuffix(params.BaseUrl, "/")
		}
	}
	if params.ShowVersion {'''

    success = success and patch_file(env_config_path, env_search_1, env_replace_1, 'Socket               string `id:"socket"')
    success = success and patch_file(env_config_path, env_search_2, env_replace_2, 'params.BaseUrl == ""')

    # 2. 适配 server/router/index.go
    router_path = "v2rayA/service/server/router/index.go"
    
    router_search_1 = '''func ServeGUI(r gin.IRoutes) {
	webDir := conf.GetEnvironmentConfig().WebDir'''
    router_replace_1 = '''func ServeGUI(r gin.IRoutes) {
	prefix := ""
	if group, ok := r.(*gin.RouterGroup); ok {
		prefix = group.BasePath()
	}
	webDir := conf.GetEnvironmentConfig().WebDir'''

    router_search_2 = '\t\tss := http.StripPrefix("/static", statigz.FileServer(staticFS))'
    router_replace_2 = '''\t\tstaticPrefix := filepath.ToSlash(filepath.Join(prefix, "static"))
		if !strings.HasPrefix(staticPrefix, "/") {
			staticPrefix = "/" + staticPrefix
		}
		ss := http.StripPrefix(staticPrefix, statigz.FileServer(staticFS))'''

    router_search_3 = '''\tengine.Use(cors.New(corsConfig))
	noAuth := engine.Group("api",'''
    router_replace_3 = '''\tengine.Use(cors.New(corsConfig))
	app := conf.GetEnvironmentConfig()
	rootPath := app.BaseUrl
	if rootPath == "" {
		rootPath = "/"
	}
	root := engine.Group(rootPath)
	noAuth := root.Group("api",'''

    router_search_4 = '\tauth := engine.Group("api",'
    router_replace_4 = '\tauth := root.Group("api",'

    router_search_5 = '''\tServeGUI(engine)

	return engine.Run(conf.GetEnvironmentConfig().Address)
}'''
    router_replace_5 = '''\tServeGUI(root)

	if app.Socket != "" {
		_ = os.Remove(app.Socket)
		listener, err := net.Listen("unix", app.Socket)
		if err != nil {
			return err
		}
		_ = os.Chmod(app.Socket, 0777)
		log.Alert("v2rayA is listening at unix:%v", app.Socket)
		return http.Serve(listener, engine)
	}

	return engine.Run(conf.GetEnvironmentConfig().Address)
}'''

    success = success and patch_file(router_path, router_search_1, router_replace_1, 'prefix := ""')
    success = success and patch_file(router_path, router_search_2, router_replace_2, 'staticPrefix := filepath.ToSlash')
    success = success and patch_file(router_path, router_search_3, router_replace_3, 'root := engine.Group(rootPath)')
    success = success and patch_file(router_path, router_search_4, router_replace_4, 'auth := root.Group("api",')
    success = success and patch_file(router_path, router_search_5, router_replace_5, 'if app.Socket != "" {')

    # 3. 适配 db/configure/configure.go
    db_config_path = "v2rayA/service/db/configure/configure.go"
    db_search_1 = '''		Ports: Ports{
			Socks5:        20170,
			Socks5WithPac: 0,
			Http:          20171,
			HttpWithPac:   20172,
			Vmess:         0,
		},'''
    db_replace_1 = '''		Ports: Ports{
			Socks5:        0,
			Socks5WithPac: 0,
			Http:          0,
			HttpWithPac:   20172,
			Vmess:         0,
		},'''

    db_search_2 = '''func GetPortsNotNil() *Ports {
	p := new(Ports)
	_ = db.Get("system", "ports", &p)
	if p == nil {
		p = new(Ports)
		p.Socks5 = 20170
		p.Http = 20171
		p.Socks5WithPac = 0
		p.HttpWithPac = 20172
		p.Vmess = 0
		p.Api = ApiPort{Port: 0}
	}
	return p
}'''
    db_replace_2 = '''func GetPortsNotNil() *Ports {
	p := new(Ports)
	_ = db.Get("system", "ports", &p)
	if p == nil {
		p = new(Ports)
		p.Socks5 = 0
		p.Http = 0
		p.Socks5WithPac = 0
		p.HttpWithPac = 20172
		p.Vmess = 0
		p.Api = ApiPort{Port: 0}
	}
	return p
}'''

    success = success and patch_file(db_config_path, db_search_1, db_replace_1, 'Socks5:        0,')
    success = success and patch_file(db_config_path, db_search_2, db_replace_2, 'p.Socks5 = 0')

    # 4. 适配前端 gui/src/App.vue (修复反代下 WebSocket 丢失子路径 BaseUrl 问题)
    app_vue_path = "v2rayA/gui/src/App.vue"
    app_search = '      url = `${protocol}://${u.host}:${u.port\n        }/api/message?Authorization=${encodeURIComponent(localStorage["token"])}`;'
    app_replace = '''      url = `${protocol}://${u.host}:${u.port}`;
      let basePath = u.path;
      if (basePath.endsWith("/api")) {
        basePath = basePath.slice(0, -4);
      }
      url = `${protocol}://${u.host}:${u.port}${basePath}/api/message?Authorization=${encodeURIComponent(localStorage["token"])}`;'''

    success = success and patch_file(app_vue_path, app_search, app_replace, 'let basePath = u.path;')

    # 5. 适配前端 gui/src/plugins/backendPort.js (动态推导 API 反代前缀)
    backendport_path = "v2rayA/gui/src/plugins/backendPort.js"
    backendport_search = '''if (ba == null) {
  // const u = parseURL(location.href);
  // if (u.host !== "localhost" && u.host !== "local" && isIntranet(u.host)) {
  //   localStorage["backendAddress"] = `${u.protocol}://${u.host}:2017`;
  // } else {
  //   localStorage.setItem("backendAddress", "http://localhost:2017");
  // }
  localStorage.setItem("backendAddress", "");
}'''
    backendport_replace = '''let currentPrefix = "";
if (typeof window !== "undefined") {
  let path = window.location.pathname;
  const match = path.match(/^(.*)\/(?:login|setting|log|server|rule|running)?\/?$/);
  if (match) {
    currentPrefix = match[1];
  }
}
if (currentPrefix && currentPrefix !== "/") {
  localStorage.setItem("backendAddress", currentPrefix);
} else {
  if (ba == null) {
    localStorage.setItem("backendAddress", "");
  }
}'''

    success = success and patch_file(backendport_path, backendport_search, backendport_replace, 'currentPrefix = match[1];')

    # 6. 适配前端 gui/src/components/modalCustomPorts.vue (只读限制服务端地址)
    customport_path = "v2rayA/gui/src/components/modalCustomPorts.vue"
    customport_search = '''        <b-input
          ref="backendAddress"
          v-model="table.backendAddress"
          placeholder="http://localhost:2017"
          pattern="https?://.+(:\d+)?"
        >
          >
        </b-input>'''
    customport_replace = '''        <b-input
          ref="backendAddress"
          v-model="table.backendAddress"
          placeholder="http://localhost:2017"
          pattern="https?://.+(:\d+)?"
          disabled
        >
        </b-input>'''

    success = success and patch_file(customport_path, customport_search, customport_replace, 'disabled')

    # 7. 适配前端多语言提示 (gui/src/locales/zh.js)
    zh_path = "v2rayA/gui/src/locales/zh.js"
    zh_search_1 = '''      "如需修改后端运行地址(默认0.0.0.0:2017)，可添加环境变量<code>V2RAYA_ADDRESS</code>或添加启动参数<code>--address</code>。",'''
    zh_replace_1 = '''      "在飞牛 NAS 平台上，服务端地址已由系统自动配置与接管，禁止手动修改。",'''
    
    zh_search_2 = '''  about: `<p>v2rayA 是 V2Ray 的一个 Web 客户端。</p>
          <p class="about-small">默认端口：</p>
          <p class="about-small">2017: v2rayA后端端口</p>
          <p class="about-small">20170: SOCKS协议</p>
          <p class="about-small">20171: HTTP协议</p>
          <p class="about-small">20172: 带分流规则的HTTP协议</p>
          <p class="about-small">其他端口：</p>
          <p class="about-small">32345: tproxy，透明代理所需 </p>
          <p>在使用中如果发现任何问题，欢迎<a href="https://github.com/v2rayA/v2rayA/issues">提出issue</a>.</p>
          <p>文档：<a href="https://v2raya.org">https://v2raya.org</a>.</p>`,'''
    zh_replace_2 = '''  about: `<p>v2rayA 是 V2Ray/Xray 的 Web 客户端。</p>
          <p class="about-small"><b>飞牛 NAS 专用版 (Linux x86_64 / aarch64)</b></p>
          <p class="about-small">本版本已深度适配飞牛平台，采用 Unix Domain Socket 进行后端通信，无需占用主机的 TCP 管理端口。</p>
          <p class="about-small"><b>默认端口：</b></p>
          <p class="about-small">20172: 混合/分流代理端口（仅启用该端口，其余端口已默认禁用以防冲突）</p>
          <p>在使用中如果发现任何问题，欢迎<a href="https://github.com/v2rayA/v2rayA/issues">提出issue</a>.</p>
          <p>文档：<a href="https://v2raya.org">https://v2raya.org</a>.</p>`,'''

    success = success and patch_file(zh_path, zh_search_1, zh_replace_1, '在飞牛 NAS 平台上')
    success = success and patch_file(zh_path, zh_search_2, zh_replace_2, '飞牛 NAS 专用版')

    # 8. 适配前端多语言提示 (gui/src/locales/en.js)
    en_path = "v2rayA/gui/src/locales/en.js"
    en_search_1 = '''      "Service address default as 0.0.0.0:2017 can be changed by setting environment variable <code>V2RAYA_ADDRESS</code> and command argument<code>--address</code>.",'''
    en_replace_1 = '''      "On FN-OS, the service address is automatically configured by system and editing is disabled.",'''
    
    en_search_2 = '''  about: `<p>v2rayA is a web GUI client of V2Ray.</p>
          <p class="about-small">Default ports:</p>
          <p class="about-small">2017: v2rayA service port</p>
          <p class="about-small">20170: SOCKS protocol</p>
          <p class="about-small">20171: HTTP protocol</p>
          <p class="about-small">20172: HTTP protocol with "Rule of Splitting Traffic"</p>
          <p class="about-small">Other ports：</p>
          <p class="about-small">32345: tproxy, needed by transparent proxy </p>
          <p>All data is stored in local instead of in the cloud. </p>
          <p>Problems found during use can be reported at <a href="https://github.com/v2rayA/v2rayA/issues">issues</a>.</p>
          <p>Documentation: <a href="https://v2raya.org">https://v2raya.org</a></p>`,'''
    en_replace_2 = '''  about: `<p>v2rayA is a web GUI client of V2Ray/Xray.</p>
          <p class="about-small"><b>FN-OS Dedicated Version (Linux x86_64 / aarch64)</b></p>
          <p class="about-small">This version is deeply integrated with FN-OS, communicating with the backend via Unix Domain Socket to ensure zero TCP port occupation for the management interface.</p>
          <p class="about-small"><b>Default Port:</b></p>
          <p class="about-small">20172: Mixed/Splitting proxy port (Only this port is enabled by default to prevent conflicts)</p>
          <p>All data is stored in local instead of in the cloud. </p>
          <p>Problems found during use can be reported at <a href="https://github.com/v2rayA/v2rayA/issues">issues</a>.</p>
          <p>Documentation: <a href="https://v2raya.org">https://v2raya.org</a></p>`,'''

    success = success and patch_file(en_path, en_search_1, en_replace_1, 'On FN-OS, the service address')
    success = success and patch_file(en_path, en_search_2, en_replace_2, 'FN-OS Dedicated Version')

    if success:
        print("所有文件修补完成！")
        sys.exit(0)
    else:
        print("部分文件修补失败，请检查报错！")
        sys.exit(1)

if __name__ == "__main__":
    main()
