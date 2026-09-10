# Load ROS 2 Jazzy + one CAS workspace. Usage: source ~/rap/cas/setup.sh so101|go2
robot=${1:-so101}
ws=~/rap/cas/${robot}_ws
[ -d $ws ] || { echo "cas: no workspace $ws"; return 1; }
[ -n "$VIRTUAL_ENV" ] && deactivate                   # other venvs break colcon/ros2
[ -n "$CONDA_DEFAULT_ENV" ] && conda deactivate
[ -z "$DISPLAY" ] && export DISPLAY=:0                # SSH: show windows on the web desktop
source /opt/ros/jazzy/setup.bash
case $robot in
  so101) export ROS_DOMAIN_ID=42 ;;
  go2)   export ROS_DOMAIN_ID=0  ;;
esac
[ -f $ws/install/setup.bash ] && source $ws/install/setup.bash
rosdep check --from-paths $ws/src --ignore-src -q >/dev/null 2>&1 \
  || echo "cas: dependencies missing (pod restarted?) -> rosdep install --from-paths src --ignore-src -r -y"
cd $ws
