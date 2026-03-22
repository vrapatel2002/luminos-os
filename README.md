# Luminos OS

An AI-native, security-first Linux operating
system. Built from scratch on Ubuntu LTS.

## What Makes Luminos Different

Every binary you run is automatically classified
and routed to the correct execution zone:
- Zone 1: Native Linux — zero overhead
- Zone 2: Wine/Proton — Windows apps,
  DXVK/VKD3D auto-applied
- Zone 3: Firecracker microVM — kernel-level
  apps in isolated quarantine

The AI layer runs permanently on your AMD XDNA
NPU at ~5W — zero impact on gaming or compute.

## Hardware Requirements

Minimum:
- CPU: x86_64, 4 cores
- RAM: 8GB
- Storage: 40GB
- GPU: Vulkan-capable

Recommended (full feature set):
- CPU: AMD Ryzen AI (XDNA NPU)
- RAM: 16GB+
- GPU: NVIDIA (6GB+ VRAM) for HIVE models
- iGPU: AMD RDNA for display + upscaling

## Building the ISO

Requires Ubuntu host with sudo:

git clone https://github.com/[your-repo]/luminos
cd luminos
sudo bash scripts/build_iso.sh
sudo bash scripts/verify_iso.sh \
  build/luminos-os-v0.1.0.iso

Build time: ~45-90 minutes depending on hardware.
Output: build/luminos-os-v0.1.0.iso (~3GB)

## Testing in VirtualBox

1. Create VM: Linux 64-bit, 4GB RAM, 50GB disk
2. Enable: EFI, Nested VT-x, 3D acceleration
3. Boot from luminos-os-v0.1.0.iso
4. First run setup launches automatically

Testing in QEMU (faster):
qemu-system-x86_64 -m 4G -smp 4 \
  -enable-kvm -cpu host \
  -cdrom luminos-os-v0.1.0.iso \
  -boot d -vga virtio \
  -display gtk,gl=on

## Current Status

Complete:
- AI daemon + zone routing
- Binary classifier (rule-based)
- Sentinel security monitor
- Wine/Proton Zone 2 with DXVK/VKD3D
- Firecracker Zone 3 infrastructure
- GPU manager (Apple-style lazy loading)
- PowerBrain (thermal + battery aware)
- Full desktop GUI (bar, dock, launcher,
  notifications, quick settings, store,
  settings, lock screen, wallpaper engine)

Stubbed (needs real hardware):
- ONNX classifier on AMD XDNA NPU
- HIVE model loading (needs GGUF files)
- Firecracker VM boot (needs vmlinux + rootfs)

## Project Structure

src/daemon/       AI orchestration daemon
src/classifier/   Binary zone classifier
src/sentinel/     Security monitor
src/zone1/        Native Linux
src/zone2/        Wine/Proton + DXVK
src/zone3/        Firecracker microVM
src/gpu_manager/  VRAM management
src/power_manager/PowerBrain
src/compositor/   Wayland + display
src/gui/          Full desktop shell
systemd/          Service files
scripts/          Build + install scripts
build/            ISO output (gitignored)
tests/            757 tests, all passing

## Contributing

Luminos is open source. PRs welcome.
Focus areas: NPU classifier training,
HIVE model fine-tuning, hardware testing.

## License
MIT License — see LICENSE file.
