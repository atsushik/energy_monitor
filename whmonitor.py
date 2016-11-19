#!/usr/bin/python
# -*- coding: utf-8 -*-

# http://qiita.com/osamasao/items/a38707465e8f8a9948ed

import time
import math
from collections import deque
import copy
import sys
import datetime
import urllib
import urllib2
import bz2
import Adafruit_ADS1x15
import RPi.GPIO as GPIO


# 電力計測の関連定数
#MEASURE_INTERVAL = 60
MEASURE_INTERVAL = 1
CHANNEL_CHANGE_INTERVAL = 10
CONVERSION_CONSTANT = 30 # 100 ohm
VOLTAGE = 100
TO_KILOWATT = 0.001

# ハートビート関連定数 ( slee-Pi 用)
FLIP_INTERVAL = 500
HEARTBEAT_GPIO = 5

# ADC1015 関連定数
I2C_BUSNUM = 1
ADS1015_I2C_BASE_ADDRESS = 0x48
SENSORS = 2
PGA_GAIN = 2
SAMPLING_RATE = 3300

# データ送信関連定数
MINIMUM_UPLOAD_QUEUE_LENGTH = 5
UPLOAD_URL = "https://[データ受信サーバーのホスト名]/whupdate.cgi"
BASICAUTH_ID = "[基本認証のID]"
BASICAUTH_PASS = "[基本認証のパスワード]"
COMPRESSION_LEVEL = 9



class Recorder:
    """このクラスは、データを Web サーバーへアップロードします。
    内部にキューを持ち、record() メソッドで受け取ったリストを保持します。
    キューが十分な長さになると、データを Web サーバーへ送信します。
    送信に失敗した場合は、次の記録タイミングで送信を試みます。
    """

    def __init__(self, url, ba_id, ba_pass, minimum_upload_queue_length = 1):
        self.data_queue = deque()

        self.url = url
        self.ba_id = ba_id
        self.ba_pass = ba_pass
        self.compression_level = COMPRESSION_LEVEL
        self.minimum_upload_queue_length = minimum_upload_queue_length


    def record(self, data):
        self.data_queue.append(self.__build_message(data))
        tmp_queue=copy.deepcopy(self.data_queue)

        try:
            if self.minimum_upload_queue_length <= len(tmp_queue) :
                self.__send_queue(tmp_queue)
                for dummy in tmp_queue:
                    self.data_queue.popleft()
        except:
            print("=== データを送信できませんでした。 ===")
            d=datetime.datetime.today()
            print d.strftime("%Y-%m-%d %H:%M:%S"),'\n'


    def __send_queue(self, queue):
        send_string = ""
        for data in queue:
            send_string += " " + data
        response=self.__send_string(send_string)


    def __send_string(self, message):

        pswd_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        pswd_mgr.add_password(None, self.url, self.ba_id, self.ba_pass)
        opener = urllib2.build_opener(urllib2.HTTPSHandler(),
            urllib2.HTTPBasicAuthHandler(pswd_mgr))
        urllib2.install_opener(opener)

        request = urllib2.Request(self.url)
        request.add_data(bz2.compress(message,self.compression_level))

        response = urllib2.urlopen(request)
        return response.read()


    def __build_message(self, data):
        message = str(int(time.time()))
        for value in data:
            message += ":" + str(value)
        return message


class Knocker:
    """このクラスは、GPIO の出力電圧を変化させます。
    flip() メソッドが呼ばれる毎に、指定の GPIO ピンの出力をフリップします。
    """

    def __init__(self, port):
        self.port = port
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(port,GPIO.OUT)


    def flip(self):
        GPIO.output(self.port,(GPIO.input(self.port)+1)%2)



class IntervalTimer(object):
    """このクラスは、全速力で busyloop() メソッドを実行します。
    また、コンストラクタで指定した秒毎に longloop() メソッドを実行します
    """

    def __init__(self, interval = 1):
        self.interval = interval

    def busyloop(self):
        pass

    def longloop(self):
        print time.time()-self.start

    def loop(self):
        self.start=int(time.time())
        prev=self.start
        while True:
            while time.time()-prev < self.interval:
                self.busyloop()
            prev = int(time.time())
            self.longloop()


class Sampler(IntervalTimer):

    """このクラスは、メインクラスです。
    AD コンバーターの管理、データ送信、ハートビートの管理をします。
    """

    def __init__(self,interval):
        super(Sampler, self).__init__(interval)
        self.knocker = Knocker(HEARTBEAT_GPIO)
        #self.recorder = Recorder(UPLOAD_URL, BASICAUTH_ID, BASICAUTH_PASS, \
        #    MINIMUM_UPLOAD_QUEUE_LENGTH)
        self.adc = Adafruit_ADS1x15.ADS1015(\
            address=ADS1015_I2C_BASE_ADDRESS,busnum=I2C_BUSNUM)
        self.reset_valiables()


    def reset_valiables(self):
        self.sensor = 0
        self.samples = 0
        self.sample_buffer = [0]*SENSORS
        self.sample_length = [0]*SENSORS
        self.watt = [0]*SENSORS


    def busyloop(self):
        if self.samples%CHANNEL_CHANGE_INTERVAL == 0 :
            self.sensor=(self.samples/CHANNEL_CHANGE_INTERVAL)%SENSORS
            self.adc.start_adc(self.sensor, gain=PGA_GAIN, \
                data_rate=SAMPLING_RATE)
            time.sleep(2.0/SAMPLING_RATE)

        current=self.adc.get_last_result()*CONVERSION_CONSTANT

        self.sample_buffer[self.sensor] += current * current
        self.sample_length[self.sensor] += 1
        if self.samples%FLIP_INTERVAL == 0:
            self.knocker.flip()
        self.samples += 1



    def longloop(self):
        for self.sensor in range(SENSORS):
            if self.sample_length[self.sensor] == 0:
                self.watt[self.sensor]=0
            else:
                self.watt[self.sensor]=\
                    math.sqrt(self.sample_buffer[self.sensor]\
                    /self.sample_length[self.sensor])*VOLTAGE*TO_KILOWATT

        #self.recorder.record(self.watt)
	#print self.watt
        ret = []
        for idx in range(SENSORS):
            ret.append('"clamp%02d[WATT]":%.2f' % (idx, self.watt[idx]) )
        total = 0
        for idx in range(SENSORS):
            total += self.watt[idx]
        ret.append('"total[WATT]":%.2f' % total)
        print "\t".join(ret)
        self.reset_valiables()



sampler = Sampler(MEASURE_INTERVAL)
sampler.loop()

