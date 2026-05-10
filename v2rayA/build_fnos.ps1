$ErrorActionPreference = "Stop"
$V2RAYA_ROOT = Get-Item .
$GUI_DIR = Join-Path $V2RAYA_ROOT.FullName "gui"
$SERVICE_DIR = Join-Path $V2RAYA_ROOT.FullName "service"

Write-Host "--- 步骤 1: 编译前端界面 ---"
Set-Location $GUI_DIR
# 某些环境可能需要清理旧的 node_modules
# Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
npm install --legacy-peer-deps --no-audit --no-fund
npm run build

Write-Host "--- 步骤 2: 编译后端服务 ---"
Set-Location $SERVICE_DIR
$env:GOOS = "linux"
$env:CGO_ENABLED = 0

# 确保目标输出目录存在
$OUT_DIR = Join-Path $V2RAYA_ROOT.FullName "build_out"
if (-not (Test-Path $OUT_DIR)) { New-Item -ItemType Directory -Path $OUT_DIR }

# 编译 amd64 (x64)
Write-Host "正在编译 Linux amd64 (x64)..."
$env:GOARCH = "amd64"
go build -o (Join-Path $OUT_DIR "v2raya_x64") -ldflags "-s -w" .

# 编译 arm64 (ARM)
Write-Host "正在编译 Linux arm64 (ARM)..."
$env:GOARCH = "arm64"
go build -o (Join-Path $OUT_DIR "v2raya_arm64") -ldflags "-s -w" .

Write-Host "--- 步骤 3: 部署到 fnpack 目录 ---"
$FNPACK_APP = Join-Path $V2RAYA_ROOT.Parent.FullName "fnpack/app"

# 部署 x86
$X86_DEST = Join-Path $FNPACK_APP "x86"
if (-not (Test-Path $X86_DEST)) { New-Item -ItemType Directory -Path $X86_DEST }
Copy-Item (Join-Path $OUT_DIR "v2raya_x64") (Join-Path $X86_DEST "v2raya-sock") -Force
Write-Host "已部署 x64 版本到 $X86_DEST/v2raya-sock"

# 部署 arm
$ARM_DEST = Join-Path $FNPACK_APP "arm"
if (-not (Test-Path $ARM_DEST)) { New-Item -ItemType Directory -Path $ARM_DEST }
Copy-Item (Join-Path $OUT_DIR "v2raya_arm64") (Join-Path $ARM_DEST "v2raya-sock") -Force
Write-Host "已部署 arm 版本到 $ARM_DEST/v2raya-sock"

Write-Host "--- 编译与部署完成！ ---"
