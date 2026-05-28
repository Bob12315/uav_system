
gz sim -v4 -r iris_runway.sdf 

sim_vehicle.py -D -v ArduCopter -f JSON --add-param-file=$HOME/gz_ws/src/ardupilot_gazebo/config/gazebo-iris-gimbal.parm --console --out=udp:10.31.18.108:14550

gz topic -t /world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image/enable_streaming -m gz.msgs.Boolean -p "data: 1"


conda activate yolo

python3 ~/uav_project/src/yolo_app/main.py

cd ~/uav_project/src/
python3 -m app.main 



ffplay -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 /dev/video0

ffplay -fflags nobuffer -flags low_delay -framedrop -sync ext /dev/video0

gst-launch-1.0 -v \
  udpsrc port=5600 caps="application/x-rtp,media=video,encoding-name=H264,payload=96" \
  ! rtph264depay \
  ! h264parse \
  ! rtph264pay config-interval=1 pt=96 \
  ! udpsink host=10.31.18.108 port=5600