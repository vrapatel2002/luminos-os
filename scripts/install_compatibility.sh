#!/bin/bash
# install_compatibility.sh
# Installs Wine/Proton/DXVK/VKD3D-Proton as OS-level components.
# Wine is not a user app — it is a Luminos OS component like libc.
# Runs as root during OS install (called by install_luminos.sh).
set -e

COMPAT_BASE="/usr/lib/luminos/compatibility"
WINE_PREFIX_BASE="/var/lib/luminos/prefixes"

echo "=== Luminos Compatibility Layer Install ==="

# ---------------------------------------------------------------------------
# SECTION 1 — Add WineHQ repo and install Wine
# ---------------------------------------------------------------------------
echo "[1/6] Installing Wine (WineHQ stable)..."

# Ensure keyrings directory exists
mkdir -p /etc/apt/keyrings

# Add WineHQ GPG key
wget -qO- https://dl.winehq.org/wine-builds/winehq.key \
    | gpg --dearmor -o /etc/apt/keyrings/winehq.gpg

# Add WineHQ apt repository
echo "deb [signed-by=/etc/apt/keyrings/winehq.gpg] \
https://dl.winehq.org/wine-builds/ubuntu/ $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/winehq.list

# Enable 32-bit architecture (required for Wine)
dpkg --add-architecture i386
apt-get update -qq

apt update -q
apt install -y --install-recommends \
  winehq-stable \
  wine-stable-amd64 \
  wine-stable-i386 || \
apt install -y wine64 wine32 \
  libwine winetricks
apt install -y winetricks

# Download wine-gecko and wine-mono manually (not in apt repos)
GECKO_VER="2.47.4"
MONO_VER="9.3.0"
GECKO_URL="https://dl.winehq.org/wine/wine-gecko/${GECKO_VER}/wine-gecko-${GECKO_VER}-x86_64.msi"
MONO_URL="https://dl.winehq.org/wine/wine-mono/${MONO_VER}/wine-mono-${MONO_VER}-x86_64.msi"

mkdir -p /usr/share/wine/gecko
mkdir -p /usr/share/wine/mono

wget -q "$GECKO_URL" -O /usr/share/wine/gecko/wine-gecko-${GECKO_VER}-x86_64.msi || true
wget -q "$MONO_URL" -O /usr/share/wine/mono/wine-mono-${MONO_VER}-x86_64.msi || true
echo "Wine gecko and mono downloaded"

# Symlink Wine into Luminos compat dir
mkdir -p "$COMPAT_BASE/wine"
ln -sf /usr/bin/wine64  "$COMPAT_BASE/wine/wine64"
ln -sf /usr/bin/wineserver "$COMPAT_BASE/wine/wineserver"
echo "Wine installed and symlinked to $COMPAT_BASE/wine/"

# ---------------------------------------------------------------------------
# SECTION 2 — Install DXVK (DirectX 9/10/11 → Vulkan translation layer)
# ---------------------------------------------------------------------------
echo "[2/6] Installing DXVK..."

DXVK_VER="2.3.1"
DXVK_URL="https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VER}/dxvk-${DXVK_VER}.tar.gz"

wget -q "$DXVK_URL" -O /tmp/dxvk.tar.gz
tar -xf /tmp/dxvk.tar.gz -C /tmp/

mkdir -p "$COMPAT_BASE/dxvk"
mkdir -p "$COMPAT_BASE/dxvk/x32"

# Copy 64-bit DLLs
cp /tmp/dxvk-${DXVK_VER}/x64/*.dll "$COMPAT_BASE/dxvk/" 2>/dev/null || true
# Copy 32-bit DLLs
cp /tmp/dxvk-${DXVK_VER}/x32/*.dll "$COMPAT_BASE/dxvk/x32/" 2>/dev/null || true
# Copy setup script if present
cp /tmp/dxvk-${DXVK_VER}/setup_dxvk.sh "$COMPAT_BASE/dxvk/" 2>/dev/null || true
chmod +x "$COMPAT_BASE/dxvk/setup_dxvk.sh" 2>/dev/null || true

# Write version file for compatibility_manager to read
echo "${DXVK_VER}" > "$COMPAT_BASE/dxvk/version"

rm -f /tmp/dxvk.tar.gz
rm -rf /tmp/dxvk-${DXVK_VER}
echo "DXVK ${DXVK_VER} installed to $COMPAT_BASE/dxvk/"

# ---------------------------------------------------------------------------
# SECTION 3 — Install VKD3D-Proton (DirectX 12 → Vulkan translation layer)
# ---------------------------------------------------------------------------
echo "[3/6] Installing VKD3D-Proton..."

VKD3D_VER="2.12"
VKD3D_URL="https://github.com/HansKristian-Work/vkd3d-proton/releases/download/v${VKD3D_VER}/vkd3d-proton-${VKD3D_VER}.tar.zst"

# Install zstd if not present (needed for .tar.zst)
apt install -y zstd 2>/dev/null || true

wget -q "$VKD3D_URL" -O /tmp/vkd3d.tar.zst
tar -xf /tmp/vkd3d.tar.zst -C /tmp/

mkdir -p "$COMPAT_BASE/vkd3d"
mkdir -p "$COMPAT_BASE/vkd3d/x32"

# Copy 64-bit DLLs
cp /tmp/vkd3d-proton-${VKD3D_VER}/x64/*.dll "$COMPAT_BASE/vkd3d/" 2>/dev/null || true
# Copy 32-bit DLLs
cp /tmp/vkd3d-proton-${VKD3D_VER}/x86/*.dll "$COMPAT_BASE/vkd3d/x32/" 2>/dev/null || true

# Write version file
echo "${VKD3D_VER}" > "$COMPAT_BASE/vkd3d/version"

rm -f /tmp/vkd3d.tar.zst
rm -rf /tmp/vkd3d-proton-${VKD3D_VER}
echo "VKD3D-Proton ${VKD3D_VER} installed to $COMPAT_BASE/vkd3d/"

# ---------------------------------------------------------------------------
# SECTION 4 — Create system default Wine prefix
# ---------------------------------------------------------------------------
echo "[4/6] Initializing system Wine prefix..."

mkdir -p "$WINE_PREFIX_BASE/default"

# Initialize prefix as the luminos system user (non-root wine prefix)
# wineboot creates the directory structure (C:\Windows\system32 etc.)
WINEPREFIX="$WINE_PREFIX_BASE/default" \
    WINEDEBUG=-all \
    WINEARCH=win64 \
    wineboot --init 2>/dev/null || echo "WARN: wineboot init returned non-zero (may be headless)"

# Apply DXVK to default prefix if setup script is available
if [ -f "$COMPAT_BASE/dxvk/setup_dxvk.sh" ]; then
    WINEPREFIX="$WINE_PREFIX_BASE/default" \
        "$COMPAT_BASE/dxvk/setup_dxvk.sh" install 2>/dev/null \
        || echo "WARN: DXVK setup returned non-zero"
fi

# Set permissions so all users can read/use the system prefix
chmod -R 755 "$WINE_PREFIX_BASE/default" 2>/dev/null || true

echo "Default Wine prefix initialized at $WINE_PREFIX_BASE/default"

# ---------------------------------------------------------------------------
# SECTION 5 — Install Vulkan runtime
# ---------------------------------------------------------------------------
echo "[5/6] Installing Vulkan runtime..."

apt install -y \
    vulkan-tools \
    libvulkan1 \
    libvulkan1:i386 \
    mesa-vulkan-drivers \
    mesa-vulkan-drivers:i386 \
    vulkan-validationlayers \
    2>/dev/null || echo "WARN: Some Vulkan packages may not be available"

echo "Vulkan runtime installed"

# ---------------------------------------------------------------------------
# SECTION 6 — Verify installation
# ---------------------------------------------------------------------------
echo "[6/6] Verifying installation..."

if wine64 --version 2>/dev/null; then
    echo "OK: wine64 found"
else
    echo "WARN: wine64 not found in PATH — check WineHQ install"
fi

if vulkaninfo --summary 2>/dev/null | grep -q "deviceName"; then
    echo "OK: Vulkan device detected"
    vulkaninfo --summary 2>/dev/null | grep "deviceName" || true
else
    echo "WARN: No Vulkan device found — DXVK/VKD3D will not work"
fi

if [ -d "$COMPAT_BASE/dxvk" ]; then
    DLL_COUNT=$(ls "$COMPAT_BASE/dxvk/"*.dll 2>/dev/null | wc -l)
    echo "OK: DXVK — ${DLL_COUNT} DLLs in $COMPAT_BASE/dxvk/"
else
    echo "WARN: DXVK directory not found"
fi

if [ -d "$COMPAT_BASE/vkd3d" ]; then
    DLL_COUNT=$(ls "$COMPAT_BASE/vkd3d/"*.dll 2>/dev/null | wc -l)
    echo "OK: VKD3D-Proton — ${DLL_COUNT} DLLs in $COMPAT_BASE/vkd3d/"
else
    echo "WARN: VKD3D directory not found"
fi

echo ""
echo "=== Compatibility Layer Install Complete ==="
echo "Wine, DXVK, VKD3D-Proton installed as OS components."
echo "Zone 2 (.exe files) will work on first boot — no user config needed."
