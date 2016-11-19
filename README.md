# 無線LANのパワーマネージメントをOFFにする
sudo sh -c "echo options 8192cu rtw_power_mgnt=0 rtw_enusbss=1 rtw_ips_mode=1 > /etc/modprobe.d/8192cu.conf"

# SSH のタイムアウトを延長
sudo sh -c "echo ClientAliveInterval 60 >> /etc/ssh/sshd_config"
sudo sh -c "echo ClientAliveCountMax 3 >> /etc/ssh/sshd_config"

# パッケージをアップデート
sudo apt-get update
sudo apt-get upgrade

# i2c-tools をインストール
sudo apt-get install i2c-tools

# i2c のクロックレートを上げる
sudo sh -c "echo dtparam=i2c_baudrate=300000 >> /boot/config.txt"

# i2c のチェック(0x48 に反応があれば ADS1015 が反応します）
i2cdetect -y 1 

# ADS1015 のライブラリをインストール
sudo apt-get install git build-essential python-dev
git clone https://github.com/adafruit/Adafruit_Python_ADS1x15.git
cd Adafruit_Python_ADS1x15
sudo python setup.py install
sudo shutdown -h now


