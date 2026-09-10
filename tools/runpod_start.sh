#!/bin/bash
# RunPod start command for robopaas/rosdocked-jazzy-k8s:jazzy-2026hs.
#
# On newer RunPod hosts the image's GPU Xorg dies with "no screens found" and the
# desktop never starts. This runs the image's normal startup unchanged, but if
# Xorg dies it prints why to the pod log and starts a software X server (Xvfb) on
# :0 instead. The image's entrypoint only waits for an X socket on :0, so it then
# carries on (VNC, noVNC, XFCE) — Gazebo and RViz render on the CPU.
#
# Template "Container Start Command":
#   bash -c 'curl -fsSL https://raw.githubusercontent.com/michaljohnson/cas-so101/main/tools/runpod_start.sh | bash'

(
  until [ -f /var/log/Xorg.0.log ]; do sleep 2; done   # Xorg has been started
  sleep 15
  [ -S /tmp/.X11-unix/X0 ] && exit 0                    # GPU Xorg is up, nothing to do

  echo "=== cas: GPU Xorg failed. Errors from /var/log/Xorg.0.log:"
  grep -E '\(EE\)|NVIDIA\(' /var/log/Xorg.0.log | head -30
  echo "=== cas: GPU devices in the container:"
  ls -l /dev/nvidia* /dev/dri 2>&1
  echo "=== cas: starting Xvfb on :0 instead (software rendering)"
  sudo apt-get update -qq && sudo apt-get install -y -qq xvfb >/dev/null
  Xvfb :0 -screen 0 1920x1080x24 +extension GLX -nolisten tcp -ac &
) &

/etc/entrypoint.sh 2>&1
sleep infinity
