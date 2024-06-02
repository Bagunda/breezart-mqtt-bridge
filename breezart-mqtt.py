#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Диденко Александр. +79802616369, wa.me/+79802616369, t.me/+79802616369, vk.com/Bagunda. Обращайтесь если нужно что-то сделать по этой теме на коммерческой основе. Сам я УмноДомщик с громадным стажем. Могу связать всё со всем.
__author__ = "Bagunda"
__license__ = "GPL"
__version__ = "1.1.2"

import sys
# import daemon
import json
import socket
import syslog
import time
import schedule
import threading
import paho.mqtt.client as mqtt
from datetime import datetime
sys.path.insert(0,"/root/diy")
import BagMQTTClass

# define the TCP connection to the vent
TCP_IP = '192.168.0.146'
TCP_PORT = 1560
# password for vent
TCP_PASS = 28854
BUFFER_SIZE = 128
# interval auto requests unit state, sec
INTERVAL = 10 # Normaly = 30

# define the MQTT connection for communication with openHAB
BROKER = '192.168.0.126'
USERNAME = 'YohanLogin'
PASSWORD = 'YohanPass'
# prefix of MQTT topics
PREFIX = 'breezart/vent'
# string or None for auto generate
CLIENT_ID = 'BreezartVent'

DEBUG_PRINT = True
DEBUG_LEVEL = "INFO" # Уровень можно выставить INFO или ERROR. Если INFO, то выводятся дополнительные сообщения
DEBUG_MQTT = False

# global vars
temperature_min = 5
temperature_max = 45
speed_min = 1
speed_max = 10
humidity_min = 0
humidity_max = 100
is_humidifier = False
is_cooler = False
is_auto = False
is_vav = False
is_regpressvav = False
is_sceneblock = False
is_powerblock = False
numvavzone = 20
is_showhumidity = False
is_casctempreg = False
is_caschumreg = False
tpd_version = ''
contr_version = ''
VZLs = dict()
subscribed_one_count = False # Поднимаем этот флаг, если мы уже подписалить один раз, определив количество клапанов

timer = None
running = True
s = None

def bagprint(msg, level):
    if level == "LOG_ERR":
        syslog.syslog(syslog.LOG_ERR, msg)
    if level == "LOG_INFO":
        if DEBUG_LEVEL == "INFO":
            syslog.syslog(syslog.LOG_INFO, msg)
    if DEBUG_PRINT:
        print(msg)


device_id = "NUC"
ProgrammName = "breezart_mqtt"
mqtt_credential_file_path = "/root/diy/mqtt_credentials.json"
my_file = open(mqtt_credential_file_path)
my_string = my_file.read()
my_file.close()
mqtt_credentials_from_file_dict = json.loads(my_string)

MQTT_client_id_subscriber = device_id + '_bsr'


class LocalBrocker_on_message(BagMQTTClass.BagMQTTClass):
    def on_message(self, mqttc, obj, msg):
        global mqtt_client
        msg1 = "Recieved msg2: {}, topic={}, brocker={}".format(str(msg.payload), msg.topic, self.BRname)
        bagprint(msg1, "LOG_INFO")
        # if DEBUG:
        #     tologread("Recieved msg: {}, topic={}, brocker={}".format(str(msg.payload), msg.topic, self.BRname))
        payload = msg.payload.decode()

        if (msg.topic == "breezart2/temp/target/set"):
            target_temp1 = msg.payload
            target_temp2 = target_temp1.decode()
            
            try:
                level = int(target_temp2)
            except ValueError:
                # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for temperature: >{0}< when try convert to int'.format(message.payload.decode('utf-8')))
                try:
                    level = int(float(target_temp2))
                except ValueError:
                    msg = 'Incorrect value for temperature: >{0}<'.format(target_temp2)
                    bagprint(msg, "LOG_ERR")
                    return
            # syslog.syslog(syslog.LOG_ERR, 'Success convert to float: >{0}<'.format(level))
            if level not in range(temperature_min, temperature_max + 1):
                msg = 'Value for temperature out of range ({0}-{1}): {2}'.format(temperature_min, temperature_max, level)
                bagprint(msg, "LOG_ERR")
                return
            print (level)
            send_data(mqtt_client, 'VWTmp_{0:X}_{1:X}'.format(TCP_PASS, level),
                    'OK_VWTmp_{0:X}'.format(level), 'Can\'t set temperature level: {0}<<<'.format(level))

        if (msg.topic == "breezart2/mode/set"):
            """
            Код запроса клиента: VWPwr_Pass_X
            Запрос на изменение состояние (включения / отключения) установки
            Описание переменных X = 11 – Включить питание, X = 10 – Отключить питание.
            Код ответа при корректном запросе ОК_VWPwr_X , где X – переданное значение (10 или 11)

            
            Код запроса клиента: VWFtr_Pass_bitFeature
            Запрос на изменение режима работы и вкл. / откл. функций
            Описание переменных:
                bitFeature:
                    Bit 2-0 – ModeSet - режим работы:
                        1 – Обогрев
                        2 – Охлаждение
                        3 – Авто
                        4 – Отключено (без обогрева и охлаждения)
                        0 – режим остается без изменений.
            """
            match payload.upper():
                case "HEAT":
                    mode = 1
                case "COOL":
                    mode = 2
                case "AUTO":
                    mode = 3
                case "FAN_ONLY":
                    mode = 4
                case "OFF":
                    mode = 10

            try:
                mode = int(mode)
            except ValueError:
                msg = 'Incorrect value for vent mode: {0}'.format(mode)
                bagprint(msg, "LOG_ERR")
                return
            if mode == 2 and not is_cooler:
                msg = 'Can\'t change vent mode, cooler is not found'
                bagprint(msg, "LOG_ERR")
                return
            if mode == 3 and not is_auto:
                msg = 'Can\'t change vent mode, auto mode is disabled'
                bagprint(msg, "LOG_ERR")
                return
            if mode not in (1, 2, 3, 4, 10):
                msg = 'Can\'t change vent mode, mode is unknown'
                bagprint(msg, "LOG_ERR")
                return
            
            if is_power == False:
                mode2 = 11
                if is_powerblock:
                    msg = 'Can\'t change power on, power is blocked'
                    bagprint(msg, "LOG_ERR")
                    return
                send_data(mqtt_client, 'VWPwr_{0:X}_{1:X}'.format(TCP_PASS, mode2),
                        'OK_VWPwr_{0:X}'.format(mode2), 'Can\'t change power state: {0}'.format(mode2))

            send_data(mqtt_client, 'VWFtr_{0:X}_{1:X}'.format(TCP_PASS, mode),
                    'OK_VWFtr_{0:X}'.format(mode), 'Can\'t change vent mode: {0}'.format(mode))

            if mode == 10:
                if is_powerblock:
                    msg = 'Can\'t change power off, power is blocked'
                    bagprint(msg, "LOG_ERR")
                    return
                send_data(mqtt_client, 'VWPwr_{0:X}_{1:X}'.format(TCP_PASS, mode),
                        'OK_VWPwr_{0:X}'.format(mode), 'Can\'t change power state: {0}'.format(mode))


        if (msg.topic == "breezart2/fanspeed/set"):
            """
            Код запроса клиента: VWSpd_Pass_SpeedTarget
            Запрос для изменения заданной скорости вентилятора.
            Описание переменных:
                SpeedTarget – заданная скорость (от SpeedMin до SpeedMax)
            """
            try:
                level = int(payload)
            except ValueError:
                # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for speed: >{0}< when try convert to int'.format(payload))
                try:
                    level = int(float(payload))
                except ValueError:
                    msg = 'Incorrect value for speed: >{0}<'.format(payload)
                    bagprint(msg, "LOG_ERR")
                    return
            # syslog.syslog(syslog.LOG_ERR, 'Success convert speed to float: >{0}<'.format(level))
            if level not in range(speed_min, speed_max + 1):
                msg = 'Value for speed out of range ({0}-{1}): {2}'.format(speed_min, speed_max, level)
                bagprint(msg, "LOG_ERR")
                return
            if is_vav and not is_regpressvav:
                msg = 'Can\'t set speed, VAV activated and pressure regulation not activated.'
                bagprint(msg, "LOG_ERR")
                return
            send_data(mqtt_client, 'VWSpd_{0:X}_{1:X}'.format(TCP_PASS, level),
                    'OK_VWSpd_{0:X}'.format(level), 'Can\'t set speed level: {0}'.format(level))


        if ("breezart2/valves/" in msg.topic):
            """
            Код запроса клиента: VWZon_Pass_SpeedTarget_iZone_LZone
            Запрос для изменения заданного расхода в зоне VAV с номером iZone. Запрос разрешен только если IsVAV == 1 И iZone<=NZoneVAV

            Описание переменных:
                SpeedTarget – заданная скорость (от SpeedMin до SpeedMax) или 15, если скорость изменять не нужно.
                iZone – номер зоны (от 1 до 20, при условии, что iZone<=NZoneVAV)
                LZone – заданный расход воздуха в зоне iZone. Значения от 0 до 100 (соответствует расходу от 0 до
                100%) или 255, если расход изменять не нужно.
            """
            mtopic = (msg.topic)
            if is_vav:
                data_array = mtopic.split('/')
                iZone = int(data_array[2])

                if payload == 'OFF':
                    LZone = 0
                elif payload == 'ON':
                    LZone = 100
                else:
                    try:
                        LZone = int(payload)
                    except ValueError:
                        # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for air flow: >{0}< when try convert to int'.format(payload))
                        try:
                            LZone = int(float(payload))
                        except ValueError:
                            msg = 'Incorrect value for air flow: >{0}<'.format(payload)
                            bagprint(msg, "LOG_ERR")
                            return
                        # syslog.syslog(syslog.LOG_ERR, 'Success convert air flow to float: >{0}<'.format(LZone))
                if LZone not in range(0, 100 + 1):
                    msg = 'Value for air flow out of range ({0}-{1}): {2}'.format(0, 100, LZone)
                    bagprint(msg, "LOG_ERR")
                    return
                SpeedTarget = 15 # don't change speed
                send_data(mqtt_client, 'VWZon_{0:X}_{1:X}_{2:X}_{3:X}'.format(TCP_PASS, SpeedTarget, iZone, LZone),
                    'OK_VWZon_{0:X}_{1:X}_{2:X}'.format(SpeedTarget, iZone, LZone), 'Can\'t set air flow LZone: {0}'.format(LZone))




def on_connect_mqtt(client, __userdata, __flags, __rc):
    client.publish(PREFIX + '/LWT', 'Online', 0, True)
    client.subscribe(PREFIX + '/POWER', 0)
    client.subscribe(PREFIX + '/AUTORESTART', 0)
    client.subscribe(PREFIX + '/SPEED', 0)
    client.subscribe(PREFIX + '/TEMPERATURE', 0)
    client.subscribe(PREFIX + '/HUMIDITY', 0)
    client.subscribe(PREFIX + '/HUMIDITYMODE', 0)
    client.subscribe(PREFIX + '/COMFORT', 0)
    client.subscribe(PREFIX + '/MODE', 0)
    client.subscribe(PREFIX + '/SCENE', 0)
    client.subscribe(PREFIX + '/SETDATETIME', 0)
    client.subscribe(PREFIX + '/#', 0)
    client.message_callback_add(PREFIX + '/POWER', on_power_message)
    client.message_callback_add(PREFIX + '/AUTORESTART', on_autorestart_message)
    client.message_callback_add(PREFIX + '/SPEED', on_speed_message)
    client.message_callback_add(PREFIX + '/TEMPERATURE', on_temperature_message)
    client.message_callback_add(PREFIX + '/HUMIDITY', on_humidity_message)
    client.message_callback_add(PREFIX + '/HUMIDITYMODE', on_humiditymode_message)
    client.message_callback_add(PREFIX + '/COMFORT', on_comfort_message)
    client.message_callback_add(PREFIX + '/MODE', on_mode_message)
    client.message_callback_add(PREFIX + '/SCENE', on_scene_message)
    client.message_callback_add(PREFIX + '/SETDATETIME', on_setdatetime_message)


def on_power_message(client, __userdata, message):
    """
    Код запроса клиента: VWPwr_Pass_X
    Запрос на изменение состояние (включения / отключения) установки
    Описание переменных X = 11 – Включить питание, X = 10 – Отключить питание.
    Код ответа при корректном запросе ОК_VWPwr_X , где X – переданное значение (10 или 11)
    """
    if is_powerblock:
        msg = 'Can\'t change power state, power is blocked'
        bagprint(msg, "LOG_ERR")
        return
    if message.payload.decode('utf-8').upper() not in ('ON', 'OFF'):
        msg = 'Value for power (ON/OFF) incorrect: {0}'.format(message.payload.decode('utf-8'))
        bagprint(msg, "LOG_ERR")
        return
    mode = 10 if message.payload.decode('utf-8').upper() == "OFF" else 11
    send_data(client, 'VWPwr_{0:X}_{1:X}'.format(TCP_PASS, mode),
              'OK_VWPwr_{0:X}'.format(mode), 'Can\'t change power state: {0}'.format(mode))


def on_speed_message(client, __userdata, message):
    """
    Код запроса клиента: VWSpd_Pass_SpeedTarget
    Запрос для изменения заданной скорости вентилятора.
    Описание переменных:
        SpeedTarget – заданная скорость (от SpeedMin до SpeedMax)
    """
    try:
        level = int(message.payload.decode('utf-8'))
    except ValueError:
        # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for speed: >{0}< when try convert to int'.format(message.payload.decode('utf-8')))
        try:
            level = int(float(message.payload.decode('utf-8')))
        except ValueError:
            msg = 'Incorrect value for speed: >{0}<'.format(message.payload.decode('utf-8'))
            bagprint(msg, "LOG_ERR")
            return
    # syslog.syslog(syslog.LOG_ERR, 'Success convert speed to float: >{0}<'.format(level))
    if level not in range(speed_min, speed_max + 1):
        msg = 'Value for speed out of range ({0}-{1}): {2}'.format(speed_min, speed_max, level)
        bagprint(msg, "LOG_ERR")
        return
    if is_vav and not is_regpressvav:
        msg = 'Can\'t set speed, VAV activated and pressure regulation not activated.'
        bagprint(msg, "LOG_ERR")
        return
    send_data(client, 'VWSpd_{0:X}_{1:X}'.format(TCP_PASS, level),
              'OK_VWSpd_{0:X}'.format(level), 'Can\'t set speed level: {0}'.format(level))


def on_temperature_message(client, __userdata, message):
    """
    Код запроса клиента: VWTmp_Pass_TempTarget
    Запрос для изменения заданной температуры
    Описание переменных:
        TempTarget – заданная температура (от TempMin до TempMax)
    """
    # payload_111 =
    # if isinstance (payload_111, int):


    try:
        level = int(message.payload.decode('utf-8'))
    except ValueError:
        # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for temperature: >{0}< when try convert to int'.format(message.payload.decode('utf-8')))
        try:
            level = int(float(message.payload.decode('utf-8')))
        except ValueError:
            msg = 'Incorrect value for temperature: >{0}<'.format(message.payload.decode('utf-8'))
            bagprint(msg, "LOG_ERR")
            return
    # syslog.syslog(syslog.LOG_ERR, 'Success convert to float: >{0}<'.format(level))
    if level not in range(temperature_min, temperature_max + 1):
        msg = 'Value for temperature out of range ({0}-{1}): {2}'.format(temperature_min, temperature_max, level)
        bagprint(msg, "LOG_ERR")
        return
    send_data(client, 'VWTmp_{0:X}_{1:X}'.format(TCP_PASS, level),
              'OK_VWTmp_{0:X}'.format(level), 'Can\'t set temperature level: {0}'.format(level))


def on_message(client, __userdata, message):
    """
    Код запроса клиента: VWZon_Pass_SpeedTarget_iZone_LZone
    Запрос для изменения заданного расхода в зоне VAV с номером iZone. Запрос разрешен только если IsVAV == 1 И iZone<=NZoneVAV

    Описание переменных:
        SpeedTarget – заданная скорость (от SpeedMin до SpeedMax) или 15, если скорость изменять не нужно.
        iZone – номер зоны (от 1 до 20, при условии, что iZone<=NZoneVAV)
        LZone – заданный расход воздуха в зоне iZone. Значения от 0 до 100 (соответствует расходу от 0 до
        100%) или 255, если расход изменять не нужно.
    """

    #syslog.syslog(syslog.LOG_INFO, message)

    mtopic = (message.topic)
    if '/VAVset/' in mtopic:
        if is_vav:
            data_array = mtopic.split('/')
            iZone = int(data_array[3])

            if data_array[4] == 'LZone':

                if message.payload.decode('utf-8') == 'OFF':
                    LZone = 0
                elif message.payload.decode('utf-8') == 'ON':
                    LZone = 100
                else:
                    try:
                        LZone = int(message.payload.decode('utf-8'))
                    except ValueError:
                        # syslog.syslog(syslog.LOG_ERR, 'Incorrect value for air flow: >{0}< when try convert to int'.format(message.payload.decode('utf-8')))
                        try:
                            LZone = int(float(message.payload.decode('utf-8')))
                        except ValueError:
                            msg = 'Incorrect value for air flow: >{0}<'.format(message.payload.decode('utf-8'))
                            bagprint(msg, "LOG_ERR")
                            return
                        # syslog.syslog(syslog.LOG_ERR, 'Success convert air flow to float: >{0}<'.format(LZone))
                if LZone not in range(0, 100 + 1):
                    msg = 'Value for air flow out of range ({0}-{1}): {2}'.format(0, 100, LZone)
                    bagprint(msg, "LOG_ERR")
                    return
                SpeedTarget = 15 # don't change speed
                send_data(client, 'VWZon_{0:X}_{1:X}_{2:X}_{3:X}'.format(TCP_PASS, SpeedTarget, iZone, LZone),
                    'OK_VWZon_{0:X}_{1:X}_{2:X}'.format(SpeedTarget, iZone, LZone), 'Can\'t set air flow LZone: {0}'.format(LZone))

                #syslog.syslog(syslog.LOG_INFO, "Horray!")


    #zone_num = data_array[2]
    #syslog.syslog(syslog.LOG_INFO, zone_num)
    #syslog.syslog(syslog.LOG_INFO, mtopic)
    #syslog.syslog(syslog.LOG_INFO, zone_num)

    #mpl = (message.payload.decode('utf-8'))
    #syslog.syslog(syslog.LOG_INFO, mpl)

    #send_data(client, 'VWZon_{0:X}_{1:X}_{2:X}_{3:X}'.format(TCP_PASS, SpeedTarget, iZone, LZone),
    #          'OK_VWTmp_{0:X}'.format(level), 'Can\'t set temperature level: {0}'.format(level))


def on_humidity_message(client, __userdata, message):
    """
    Код запроса клиента: VWHum_Pass_HumTarget
    Запрос для заданной влажности. Запрос разрешен только если IsHumid == 1
    Описание переменных:
        HumTarget – заданная влажность (от HumMin до HumMax)
    """
    if not is_humidifier:
        msg = 'Can\'t set humidity, humidifier not found'
        bagprint(msg, "LOG_ERR")
        return
    try:
        level = int(message.payload.decode('utf-8'))
    except ValueError:
        msg = 'Incorrect value for humidity: {0}'.format(message.payload.decode('utf-8'))
        bagprint(msg, "LOG_ERR")
        return
    if level not in range(humidity_min, humidity_max + 1):
        msg = 'Value for humidity out of range ({0}-{1}): {2}'.format(humidity_min, humidity_max, level)
        bagprint(msg, "LOG_ERR")
        return
    send_data(client, 'VWHum_{0:X}_{1:X}'.format(TCP_PASS, level),
              'OK_VWHum_{0:X}'.format(level), 'Can\'t set humidity level: {0}'.format(level))


def on_comfort_message(client, __userdata, message):
    """
    Код запроса клиента: VWFtr_Pass_bitFeature
    Запрос на изменение режима работы и вкл. / откл. функций
    Описание переменных:
        bitFeature:
            Bit 6-5 – Комфорт:
                1 – Включено
                2 – Отключено
                0 -  без изменений.
    """
    if message.payload.decode('utf-8').upper() not in ('ON', 'OFF'):
        return
    mode = 1 if message.payload.decode('utf-8').upper() == 'ON' else 2
    send_data(client, 'VWFtr_{0:X}_{1:X}'.format(TCP_PASS, mode << 5),
              'OK_VWFtr_{0:X}'.format(mode << 5), 'Can\'t change comfort mode: {0}'.format(mode))


def on_autorestart_message(client, __userdata, message):
    """
    Код запроса клиента: VWFtr_Pass_bitFeature
    Запрос на изменение режима работы и вкл. / откл. функций
    Описание переменных:
        Bit 8-7 – Рестарт:
            1 – Включено
            2 – Отключено
            0 – без изменений
    """
    if message.payload.decode('utf-8').upper() not in ('ON', 'OFF'):
        return
    mode = 1 if message.payload.decode('utf-8').upper() == 'ON' else 2
    send_data(client, 'VWFtr_{0:X}_{1:X}'.format(TCP_PASS, mode << 7),
              'OK_VWFtr_{0:X}'.format(mode << 7), 'Can\'t change autorestart mode: {0}'.format(mode))


def on_humiditymode_message(client, __userdata, message):
    """
    Код запроса клиента: VWFtr_Pass_bitFeature
    Запрос на изменение режима работы и вкл. / откл. функций
    Описание переменных:
        Bit 4-3 – HumidSet - Увлажнитель:
            1 – Включен (Авто)
            2 – Отключен
            0 – без изменений.
    """
    if message.payload.decode('utf-8').upper() not in ('ON', 'OFF'):
        return
    mode = 1 if message.payload.decode('utf-8').upper() == 'ON' else 2
    send_data(client, 'VWFtr_{0:X}_{1:X}'.format(TCP_PASS, mode << 3),
              'OK_VWFtr_{0:X}'.format(mode << 3), 'Can\'t change humidity mode: {0}'.format(mode))


def on_mode_message(client, __userdata, message):
    """
    Код запроса клиента: VWFtr_Pass_bitFeature
    Запрос на изменение режима работы и вкл. / откл. функций
    Описание переменных:
        bitFeature:
            Bit 2-0 – ModeSet - режим работы:
                1 – Обогрев
                2 – Охлаждение
                3 – Авто
                4 – Отключено (без обогрева и охлаждения)
                0 – режим остается без изменений.
    """
    try:
        mode = int(message.payload.decode('utf-8'))
    except ValueError:
        msg = 'Incorrect value for vent mode: {0}'.format(message.payload.decode('utf-8'))
        bagprint(msg, "LOG_ERR")
        return
    if mode == 2 and not is_cooler:
        msg = 'Can\'t change vent mode, cooler is not found'
        bagprint(msg, "LOG_ERR")
        return
    if mode == 3 and not is_auto:
        msg = 'Can\'t change vent mode, auto mode is disabled'
        bagprint(msg, "LOG_ERR")
        return
    if mode not in (1, 2, 3, 4):
        msg = 'Can\'t change vent mode, mode is unknown'
        bagprint(msg, "LOG_ERR")
        return
    send_data(client, 'VWFtr_{0:X}_{1:X}'.format(TCP_PASS, mode),
              'OK_VWFtr_{0:X}'.format(mode), 'Can\'t change vent mode: {0}'.format(mode))


def on_scene_message(client, __userdata, message):
    """
    Код запроса клиента: VWScn_Pass_bitNScen
    Запрос для активации сценария. Запрос разрешен, только если ScenBlock == 0
    Описание переменных:
        bitNScen:
            Bit 3-0 – номер сценария, который нужно активировать (от 1 до 8) или 0, если включать сценарий не
            нужно.
            Bit 7-4 – 10 - отключить выполнение сценариев по таймерам; 11 – включить выполнение сценариев
            по таймерам. При других значениях это поле ни на что не влияет.
    """
    if is_sceneblock:
        msg = 'Can\'t change scene, scene is blocked'
        bagprint(msg, "LOG_ERR")
        return
    mode = message.payload.decode('utf-8').upper()
    if mode in ('ON', 'OFF'):
        command = (10 if mode == 'OFF' else 11) << 4
    else:
        try:
            mode = int(mode)
        except ValueError:
            msg = 'Incorrect value for scene: {0}'.format(message.payload.decode('utf-8'))
            bagprint(msg, "LOG_ERR")
            return
        if mode in (1, 2, 3, 4, 5, 6, 7, 8):
            command = mode
        else:
            msg = 'Can\'t change scene, scene number must be in range 1-8'
            bagprint(msg, "LOG_ERR")
            return
    send_data(client, 'VWScn_{0:X}_{1:X}'.format(TCP_PASS, command),
              'OK_VWScn_{0:X}'.format(command), 'Can\'t change scene: {0}'.format(mode))


def on_setdatetime_message(client, __userdata, __message):
    """
    Код запроса клиента: VWSdt_Pass_HN_WS_MD_YY
    Запрос на установку даты и времени
    Описание переменных:
        HN – Часы (старший байт); Минуты (младший байт)
        WS – День недели (старший байт) от 1-Пн до 7-Вс; Секунды (младший байт)
        MD – Месяц (старший байт), день месяца (младший байт)
        YY – Год.
    """
    d = datetime.today()
    hour_min = (d.hour << 8) + d.minute
    week_sec = (d.isoweekday() << 8) + d.second
    month_day = (d.month << 8) + d.day
    year = d.year
    send_data(client,
              'VWSdt_{0:X}_{1:X}_{2:X}_{3:X}_{4:X}'.format(TCP_PASS, hour_min, week_sec, month_day, year),
              'OK_VWSdt_{0:X}_{1:X}_{2:X}_{3:X}'.format(hour_min, week_sec, month_day, year),
              'Can\'t set datetime on vent')


def check_vent_params():
    global temperature_min, temperature_max
    global speed_min, speed_max
    global humidity_min, humidity_max
    global is_humidifier, is_cooler, is_auto
    global is_vav, is_regpressvav, is_regpressvav_ha
    global numvavzone
    global is_showhumidity, is_casctempreg, is_caschumreg
    global tpd_version, contr_version

    '''
    Запрос: VPr07_Pass
    Ответ: VPr07_bitTempr_bitSpeed_bitHumid_bitMisc_BitPrt_BitVerTPD_BitVerContr
    '''
    data = send_request('{0}_{1:X}'.format('VPr07', TCP_PASS))
    if not data:
        msg = 'Incorrect answer 1: {0}'.format(data)
        bagprint(msg, "LOG_ERR")
        return
    data_array = split_data(data, 8)
    if not data_array:
        msg = 'Incorrect answer 2: {0}'.format(data)
        bagprint(msg, "LOG_ERR")
        return False
    '''
    Описание переменных:
        bitTemper:
            Bit 7-0 – TempMin – минимально допустимая заданная температура (от 5 до 15)
            Bit 15-8 –TempMax – максимально допустимая заданная температура (от 30 до 45)
        bitSpeed:
            Bit 7-0 – SpeedMin - минимальная скорость (от 1 до 7).
            Bit 15-8 – SpeedMax - максимальная скорость (от 2 до 10).
        bitHumid:
            Bit 7-0 – HumidMin – минимальная заданная влажность, от 0 до 100%.
            Bit 15-8 – HumidMax - максимальная заданная влажность, от 0 до 100%.
        bitMisc:
            Bit 4 - 0 – NVAVZone – кол-во зон в режиме VAV (от 1 до 20).
            Bit 7 - 5 – резерв
            Bit 8 – VAVMode – режим VAV включен.
            Bit 9 – IsRegPressVAV – включена возможность регулирования давления в канале в режиме VAV.
            Bit 10 – IsShowHum – включено отображение влажности.
            Bit 11 – IsCascRegT – включен каскадный регулятор T.
            Bit 12 – IsCascRegH – включен каскадный регулятор H.
            Bit 13 – IsHumid – есть увлажнитель.
            Bit 14 – IsCooler – есть охладитель.
            Bit 15 – IsAuto – есть режим Авто переключения Обогрев / Охлаждение.
        BitPrt:
            Bit 7-0 – ProtSubVers – субверсия протокола обмена (от 1 до 255)
            Bit 15-8 – ProtVers – версия протокола обмена (от 100 до 255)
        BitVerTPD:
            Bit 7-0 – LoVerTPD – младший байт версии прошивки пульта
            Bit 15-8 – HiVerTPD – старший байт версии прошивки пульта
        BitVerContr - Firmware_Ver – версия прошивки контроллера
    '''
    try:
        version = int(data_array[5], 16) >> 8
        subversion = int(data_array[5], 16) & 0xFF
    except ValueError:
        msg = 'Incorrect value for version/subversion'
        bagprint(msg, "LOG_ERR")
        return False
    if version != 107:
        msg = 'Incompatible protocol version: {0}.{1}'.format(version, subversion)
        bagprint(msg, "LOG_ERR")
        return False
    msg = 'Protocol version: {0}.{1}'.format(version, subversion)
    bagprint(msg, "LOG_ERR")
    tpd_version = '{0}.{1}'.format(int(data_array[6], 16) >> 8, int(data_array[6], 16) & 0xFF)
    msg = 'TPD version: {0}'.format(tpd_version)
    bagprint(msg, "LOG_INFO")
    contr_version = '{0}.{1}.{2}'.format((int(data_array[7], 16) & 0xE000) >> 13,
                                                             (int(data_array[7], 16) & 0x1FE0) >> 5,
                                                             int(data_array[7], 16) & 0x1F)
    msg = 'Controller version: {0}'.format(contr_version)
    bagprint(msg, "LOG_INFO")
    #print(data_array)
    #msg = json.dumps(data_array)
    #syslog.syslog(syslog.LOG_ERR, msg)
    try:
        temperature_min = int(data_array[1], 16) & 0xFF
        temperature_max = (int(data_array[1], 16) & 0xFF00) >> 8
        speed_min = int(data_array[2], 16) & 0xFF
        speed_max = (int(data_array[2], 16) & 0xFF00) >> 8
        humidity_min = int(data_array[3], 16) & 0xFF
        humidity_max = (int(data_array[3], 16) & 0xFF00) >> 8
        numvavzone = int(data_array[4], 16) & 0x1F
        is_vav = True if int(data_array[4], 16) & 0x100 else False
        is_regpressvav_ha = "ON" if int(data_array[4], 16) & 0x200 else "OFF"
        is_regpressvav = True if int(data_array[4], 16) & 0x200 else False
        is_showhumidity = True if int(data_array[4], 16) & 0x400 else False
        is_casctempreg = True if int(data_array[4], 16) & 0x800 else False
        is_caschumreg = True if int(data_array[4], 16) & 0x1000 else False
        is_humidifier = True if int(data_array[4], 16) & 0x2000 else False
        is_cooler = True if int(data_array[4], 16) & 0x4000 else False
        is_auto = True if int(data_array[4], 16) & 0x8000 else False
    except ValueError:
        msg = 'Incorrect value for vent parameters'
        bagprint(msg, "LOG_ERR")
        return False
    return True


def get_vent_status(client):
    global timer, VZLs, tpd_version, contr_version, is_regpressvav_ha
    global is_sceneblock, is_powerblock, is_power, speed_min, speed_max
    timer = threading.Timer(INTERVAL, get_vent_status, [client])
    timer.start()
    '''
    Запрос: VSt07_Pass
    Ответ: VSt07_bitState_bitMode_bitTempr_bitHumid_bitSpeed_bitMisc_bitTime_bitDate_bitYear_Msg
    '''
    status = dict()
    status['Temperature'] = dict()
    status['Humidity'] = dict()
    status['Speed'] = dict()
    status['DateTime'] = dict()
    status['Scene'] = dict()
    status['Settings'] = dict()
    status['State'] = dict()
    status['Sensors'] = dict()

    data = send_request('{0}_{1:X}'.format('VSt07', TCP_PASS))
    if not data:
        msg = 'Can\'t connect to vent'
        bagprint(msg, "LOG_ERR")
        status['State']['Unit'] = 'Нет связи с вентиляцией'
        client.publish(PREFIX + '/STATUS', json.dumps(status, ensure_ascii=False))
        return
    data_array = split_data(data, 11)
    if not data_array:
        msg = 'Incorrect answer 3: {0}'.format(data)
        bagprint(msg, "LOG_ERR")
        msg = 'data_array: {0}'.format(json.dumps(data_array))
        bagprint(msg, "LOG_ERR")
        return
    '''
    bitState:
        Bit 0 – PwrBtnState – состояние кнопки питания (вкл / выкл).
        Bit 1 – IsWarnErr – есть предупреждение. В Msg содержится текст сообщения.
        Bit 2 – IsFatalErr – есть критическая ошибка. В Msg содержится текст сообщения.
        Bit 3 – DangerOverheat – угроза перегрева калорифера (для установки с электрокалорифером).
        Bit 4 – AutoOff – установка автоматически выключена на 5 минут для автоподстройки нуля
        датчика давления.
        Bit 5 – ChangeFilter – предупреждение о необходимости замены фильтра.
        Bit 8-6 – ModeSet – установленный режим работы.
            1 – Обогрев
            2 – Охлаждение
            3 – Авто
            4 – Отключено (вентиляция без обогрева и охлаждения)
        Bit 9 – HumidMode – селектор Увлажнитель активен (стоит галочка).
        Bit 10 – SpeedIsDown – скорость вентилятора автоматически снижена.
        Bit 11 – FuncRestart – включена функция Рестарт при сбое питания.
        Bit 12 – FuncComfort – включена функция Комфорт.
        Bit 13 – HumidAuto – увлажнение включено (в режиме Авто).
        Bit 14 – ScenBlock – сценарии заблокированы режимом ДУ.
        Bit 15 – BtnPwrBlock – кнопка питания заблокирована режимом ДУ.
    '''
    status['State']['Power'] = 'ON' if int(data_array[1], 16) & 0x01 else 'OFF'
    is_power = "ON" if int(data_array[1], 16) & 0x01 else 'OFF'
    Warning = "ON" if int(data_array[1], 16) & 0x02 else "OFF"
    status['State']['Warning'] = Warning
    Critical = "ON" if int(data_array[1], 16) & 0x04 else 'OFF'
    status['State']['Critical'] = Critical
    Overheat = "ON" if int(data_array[1], 16) & 0x08 else 'OFF'
    status['State']['Overheat'] = Overheat
    AutoOff = "ON" if int(data_array[1], 16) & 0x10 else 'OFF'
    status['State']['AutoOff'] = AutoOff
    ChangeFilter = "ON" if int(data_array[1], 16) & 0x20 else 'OFF'
    status['State']['ChangeFilter'] = ChangeFilter
    status['Settings']['Mode'] = (int(data_array[1], 16) & 0x1C0) >> 6
    status['Humidity']['Mode'] = 'ON' if int(data_array[1], 16) & 0x200 else 'OFF'
    SpeedIsDown = 'ON' if int(data_array[1], 16) & 0x400 else 'OFF'
    status['Speed']['SpeedIsDown'] = SpeedIsDown
    status['State']['AutoRestart'] = 'ON' if int(data_array[1], 16) & 0x800 else 'OFF'
    Comfort = "ON" if int(data_array[1], 16) & 0x1000 else 'OFF'
    status['State']['Comfort'] = Comfort
    status['Humidity']['Auto'] = 'ON' if int(data_array[1], 16) & 0x2000 else 'OFF'
    is_sceneblock = True if int(data_array[1], 16) & 0x4000 else False
    status['Scene']['Block'] = 'ON' if is_sceneblock else 'OFF'
    is_powerblock = True if int(data_array[1], 16) & 0x8000 else False
    is_powerblock_ha = 'ON' if int(data_array[1], 16) & 0x8000 else 'OFF'
    status['State']['PowerBlock'] = 'ON' if is_powerblock else 'OFF'
    LocalBrocker.bag_pub("Warning",        Warning,          retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("AutoOff",        AutoOff,          retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("Comfort",        Comfort,          retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("Critical",       Critical,         retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("is_power",       is_power,         retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("Overheat",       Overheat,         retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("SpeedIsDown",    SpeedIsDown,      retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("ChangeFilter",   ChangeFilter,     retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("is_powerblock",  is_powerblock_ha, retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("is_regpressvav", is_regpressvav_ha,retain = False, use_topic_header = True)
    '''
    bitMode:
        Bit 1, 0 – UnitState – состояние установки:
            0 – Выключено.
            1 – Включено.
            2 – Выключение (переходный процесс перед отключением).
            3 – Включение (переходный процесс перед включением).
        Bit 2 – SceneAllow – разрешена работа по сценариям.
        Bit 5-3 – Mode – режим работы:
            0 – Обогрев
            1 – Охлаждение
            2 – Авто-Обогрев
            3 – Авто-Охлаждение
            4 – Отключено (вентиляция без обогрева и охлаждения)
            5 – Нет (установка выключена)
        Bit 9-6 – NumActiveScene – номер активного сценария (от 1 до 8), 0 если нет.
        Bit 12-10 – WhoActivateScene – кто запустил (активировал) сценарий:
            0 – активного сценария нет и запущен не будет
            1 – таймер1
            2 – таймер2
            3 – пользователь вручную
            4 – сценарий будет запущен позднее (сейчас активного сценария нет)
        Bit 13-15 – NumIcoHF – номер иконки Влажность / фильтр.
    '''
    unitstate_dict = {0: 'Выключено', 1: 'Включено', 2: 'Выключение', 3: 'Включение'}
    UnitState_int = (int(data_array[2], 16) & 0x03)
    status['UnitState'] = UnitState_int
    unitstate_str = unitstate_dict[UnitState_int]
    LocalBrocker.bag_pub("UnitState", unitstate_str, retain = False, use_topic_header = True)

    status['Scene']['SceneState'] = 'ON' if int(data_array[2], 16) & 0x04 else 'OFF'
    unitmode_dict =       {0: 'Обогрев', 1: 'Охлаждение', 2: 'Авто-Обогрев', 3: 'Авто-Охлаждение', 4: 'Вентиляция', 5: 'Выключено'}
    unitmode_arr_homas = {0: 'heat',    1: 'cool',       2: 'auto',    3: 'auto',       4: 'fan_only',   5: 'off'}
    unitmode_int = (int(data_array[2], 16) & 0x38) >> 3
    unitmode_homas = unitmode_arr_homas[unitmode_int]
    unitmode_str = unitmode_dict[unitmode_int]

    LocalBrocker.bag_pub("mode/state", unitmode_homas, retain = False, use_topic_header = True)
    LocalBrocker.bag_pub("mode/state_string", unitmode_str, retain = False, use_topic_header = True)
    status['Mode'] = (int(data_array[2], 16) & 0x38) >> 3
    status['Scene']['Number'] = (int(data_array[2], 16) & 0x3C0) >> 6
    status['Scene']['WhoActivate'] = (int(data_array[2], 16) & 0x1C00) >> 10
    status['State']['IconHF'] = (int(data_array[2], 16) & 0xE000) >> 13
    '''
    bitTempr:
        Bit 7-0 – Tempr signed char – текущая температура, °С. Диапазон значений от -50 до 70.
        Bit 15-8 – TemperTarget – заданная температура, °С. Диапазон значений от 0 до 50.
    '''
    status['Temperature']['Current'] = int(data_array[3], 16) & 0xFF
    LocalBrocker.bag_pub("temp/current/state", status['Temperature']['Current'], retain = False, use_topic_header = True)
    status['Temperature']['Target'] = (int(data_array[3], 16) & 0xFF00) >> 8
    LocalBrocker.bag_pub("temp/target/state", status['Temperature']['Target'], retain = False, use_topic_header = True)
    '''
    bitHumid:
        Bit 7-0 – Humid – текущая влажность (при наличии увлажнители или датчика влажности). Диапазон
        значений от 0 до 100. При отсутствии данных значение равно 255.
        Bit 15-8 – HumidTarget – заданная влажность. Диапазон значений от 0 до 100.
    '''
    status['Humidity']['Current'] = int(data_array[4], 16) & 0xFF
    status['Humidity']['Target'] = (int(data_array[4], 16) & 0xFF00) >> 8
    '''
    bitSpeed:
        Bit 3-0 – Speed – текущая скорость вентилятора, диапазон от 0 до 10.
        Bit 7-4 – SpeedTarget – заданная скорость вентилятора, диапазон от 0 до 10.
        Bit 15-8 – SpeedFact – фактическая скорость вентилятора 0 – 100%. Если не определено, то 255.
    '''
    status['Speed']['Current'] = int(data_array[5], 16) & 0x0F
    status['Speed']['Target'] = (int(data_array[5], 16) & 0xF0) >> 4
    status['Speed']['Actual'] = (int(data_array[5], 16) & 0xFF00) >> 8
    LocalBrocker.bag_pub("fanspeed/state", status['Speed']['Current'], retain = False, use_topic_header = True)
    '''
    bitMisc:
        Bit 3-0 – TempMin – минимально допустимая заданная температура (от 5 до 15). Может изменяться
        в зависимости от режима работы вентустановки
        Bit 5, 4 – ColorMsg – иконка сообщения Msg для различных состояний установки:
            0 – Нормальная работа (серый)
            1 – Предупреждение (желтый)
            2 – Ошибка (красный)
        Bit 7, 6 – ColorInd – цвет индикатора на кнопке питания для различных состояний установки:
            0 – Выключено (серый)
            1 – Переходный процесс включения / отключения (желтый)
            2 – Включено (зеленый)
        Bit 15-8 – FilterDust – загрязненность фильтра 0 - 250%, если не определено, то 255.
    '''
    status['Temperature']['Minimum'] = int(data_array[6], 16) & 0x0F
    status['State']['ColorMsg'] = (int(data_array[6], 16) & 0x30) >> 4
    status['State']['ColorInd'] = (int(data_array[6], 16) & 0xC0) >> 6
    FilterDust = (int(data_array[6], 16) & 0xFF00) >> 8
    status['State']['FilterDust'] = FilterDust
    LocalBrocker.bag_pub("FilterDust", FilterDust, retain = False, use_topic_header = True)
    '''
    bitTime:
        Bit 7-0 – nn – минуты (от 00 до 59)
        Bit 15-8 – hh – часы (от 00 до 23)
    '''
    status['DateTime']['Time'] = '{0:02d}:{1:02d}'.format((int(data_array[7], 16) & 0xFF00) >> 8,
                                                          int(data_array[7], 16) & 0xFF)
    '''
    bitDate:
        Bit 7-0 – dd – день месяца (от 1 до 31)
        Bit 15-8 – mm – месяц (от 1 до 12)
    bitYear:
        Bit 7-0 – dow – день недели (от 1-Пн до 7-Вс)
        Bit 15-8 – yy – год (от 0 до 99, последние две цифры года).
    '''
    status['DateTime']['Date'] = '{0:02d}-{1:02d}-20{2:02d}'.format(int(data_array[8], 16) & 0xFF,
                                                                    (int(data_array[8], 16) & 0xFF00) >> 8,
                                                                    (int(data_array[9], 16) & 0xFF00) >> 8)
    '''
    Msg (Unit_msg) - текстовое сообщение о состоянии установки длиной от 5 до 70 символов.
    '''
    Unit_msg = data_array[10].strip()
    status['Msg'] = Unit_msg
    LocalBrocker.bag_pub("Unit_msg", Unit_msg, retain = False, use_topic_header = True)
    '''
    Vent settings
    '''
    status['Settings']['MinTemperature'] = temperature_min
    status['Settings']['MaxTemperature'] = temperature_max
    status['Settings']['MinSpeed'] = speed_min
    status['Settings']['MaxSpeed'] = speed_max
    status['Settings']['MinHumidity'] = humidity_min
    status['Settings']['MaxHumidity'] = humidity_max
    status['Settings']['isHumidifier'] = is_humidifier
    status['Settings']['isCooler'] = is_cooler
    status['Settings']['isAuto'] = is_auto
    status['Settings']['isVAV'] = is_vav
    status['Settings']['isRegPressVAV'] = is_regpressvav
    status['Settings']['isSceneBlock'] = is_sceneblock
    status['Settings']['isPowerBlock'] = is_powerblock
    status['Settings']['NumZoneVAV'] = numvavzone
    status['Settings']['isShowHumidity'] = is_showhumidity
    status['Settings']['isCascTempReg'] = is_casctempreg
    status['Settings']['isCascHumReg'] = is_caschumreg
    status['TPDVer'] = tpd_version
    status['ContVer'] = contr_version
    '''
    Запрос: VSens_Pass
    Ответ: VSens_Sens01_Sens02_Sens03_Sens04_Sens05_Sens06_Sens07_Sens08_Sens09_Sens10_Sens11_Sens12
        Sens_01 signed word – температура воздуха на выходе вентустановки х 10, °С.
            Диапазон значений от -50,0 до 70,0.
        При отсутствии корректных данных значение равно 0xFB07
        Назначение остальных параметров см.документацию.

    '''

    if tpd_version[:2] != "4.":
        #syslog.syslog(syslog.LOG_INFO, "VSens don't use on this firmware of TPD")

        time.sleep(0.5)
        data = send_request('{0}_{1:X}'.format('VSens', TCP_PASS))
        if data:
            data_array = split_data(data, 13)
            if data_array:
                status['Sensors']['Sens_01'] = (-(int(data_array[1], 16) & 0x8000) | (
                        int(data_array[1], 16) & 0x7fff)) / 10.0
                status['Sensors']['Sens_05'] = int(data_array[5], 16) / 10.0
            else:
                # if data != "VSens__127_fb07_fb07_fb07_119_fb07_fb07_0" and data != "VSens__128_fb07_fb07_fb07_11a_fb07_fb07_0" and data != "VSens__126_fb07_fb07_fb07_11a_fb07_fb07_0" and data != "VSens__125_fb07_fb07_fb07_11a_fb07_fb07_0":
                    msg = 'Incorrect answer 4: {0}'.format(data)
                    bagprint(msg, "LOG_INFO")
        else:
            msg = 'Can\'t connect to vent'
            bagprint(msg, "LOG_ERR")
            status['State']['Unit'] = 'Нет связи с вентиляцией'



    VZLs = {} # All valves
    
    for VAV_num in range(1, numvavzone+1):
        '''
        Код запроса клиента: VZL01_Pass
        Запрос о параметрах расхода воздуха в VAV зоне №1. Запрос разрешен только если IsVAV == 1. 
        Ответ сервера: VZL01_bitZConV_bitZL_CO2Fact
          bitZConV:
            Bit 3-0 - VAV_StateV – состояние зоны:
              0 – зона отключена,
              1 – ОК
              2 - нет связи с зоной
              3 - зона неактивна (т.е. номер зоны > NZone)
              4 - есть ошибки (неисправность датчика и др.)
            Bit 7-4 – VAV_TypeConV– метод формирования задания расхода воздуха:
              0 : От местного задатчика
              1 : Централизованно
              2 : Смешанно
              3 : Автоматическое по СО2
              4 : От местного переключателя "сухой контакт"
              5 : Смешанно с автопереключением (с v1.7)
            Bit 8 – VAV_MixConV – текущий способ управления расходом в смешанном режиме:
              0 : По-месту
              1 : Централизованно
            Bit 13-9 – Иконка для зоны (от 0 до 26)
          bitZL:
            Bit 7-0 – VAV_LFact – фактический расход воздуха, от 0 до 100%
            Bit 15-8 – VAV_LTarg – заданный расход воздуха, от 0 до 100%
          CO2Fact – фактическая концентрация CO2, ppm (при наличии датчика, иначе 0).
        '''
        VAV_num_z = myint2str(VAV_num, 2)
        time.sleep(0.2)
        data = send_request('{0}_{1:X}'.format('VZL' + VAV_num_z, TCP_PASS))
        if not data:
            msg = 'Can\'t connect to vent'
            bagprint(msg, "LOG_ERR")
            status['State']['Unit'] = 'Нет связи с вентиляцией'
            client.publish(PREFIX + '/STATUS', json.dumps(status, ensure_ascii=False))
            return
        data_array = split_data(data, 4)
        if not data_array:
            msg = 'Incorrect answer 5: {0}'.format(data)
            bagprint(msg, "LOG_ERR")
            msg = 'data_array: {0}'.format(json.dumps(data_array))
            bagprint(msg, "LOG_ERR")
            return

        VAV_StateV_statuses = {0: 'off', 1: 'ok', 2: 'no_connection', 3: 'isset_errors'}
        VAV_StateV_int = (int(data_array[1], 16) & 0x0F)
        VAV_StateV_text = VAV_StateV_statuses[VAV_StateV_int]

        status['VZL' + VAV_num_z] = dict()
        status['VZL' + VAV_num_z]['VAV_StateV'] = (int(data_array[1], 16) & 0x0F)
        status['VZL' + VAV_num_z]['VAV_TypeConV'] = (int(data_array[1], 16) & 0xF0) >> 4
        status['VZL' + VAV_num_z]['VAV_MixConV'] = (int(data_array[1], 16) & 0x100) >> 8
        status['VZL' + VAV_num_z]['icon'] = (int(data_array[1], 16) & 0x3E00) >> 9
        status['VZL' + VAV_num_z]['VAV_LFact'] = (int(data_array[2], 16) & 0xFF)
        status['VZL' + VAV_num_z]['VAV_LTarg'] = (int(data_array[2], 16) & 0xFF00) >> 8
        status['VZL' + VAV_num_z]['CO2Fact'] = (int(data_array[3], 16) & 0xFF)

        dict_sample = {}
        dict_sample['VAV_StateV'] = (int(data_array[1], 16) & 0x0F)
        dict_sample['VAV_StateV_text'] = VAV_StateV_text
        dict_sample['VAV_TypeConV'] = (int(data_array[1], 16) & 0xF0) >> 4
        dict_sample['VAV_MixConV'] = (int(data_array[1], 16) & 0x100) >> 8
        dict_sample['icon'] = (int(data_array[1], 16) & 0x3E00) >> 9
        dict_sample['VAV_LFact'] = (int(data_array[2], 16) & 0xFF)
        dict_sample['VAV_LTarg'] = (int(data_array[2], 16) & 0xFF00) >> 8
        dict_sample['CO2Fact'] = (int(data_array[3], 16) & 0xFF)

        VZLs[VAV_num] = dict_sample
        
        if (VZLs[VAV_num]['VAV_StateV'] == 1):
            LocalBrocker.bag_pub("valves/" + str(VAV_num) + "/availability", "online", retain = False, use_topic_header = True)
        else:
            LocalBrocker.bag_pub("valves/" + str(VAV_num) + "/availability", "offline", retain = False, use_topic_header = True)

        LocalBrocker.bag_pub("valves/" + str(VAV_num) + "/StateV",      VZLs[VAV_num]['VAV_StateV_text'], retain = False, use_topic_header = True)
        LocalBrocker.bag_pub("valves/" + str(VAV_num) + "/LevelFact",   VZLs[VAV_num]['VAV_LFact'],       retain = False, use_topic_header = True)
        LocalBrocker.bag_pub("valves/" + str(VAV_num) + "/LevelTarget", VZLs[VAV_num]['VAV_LTarg'],       retain = False, use_topic_header = True)

    client.publish(PREFIX + '/STATUS', json.dumps(status, ensure_ascii=False))
    LocalBrocker.bag_pub("STATUS", json.dumps(status, ensure_ascii=False), retain = False, use_topic_header = True)
    




def bin_to_strBin_with_00000000(value):
        b = '00000000' + ((bin(value)[2:]))
        len1 = len(b) - 8
        return b[len1:]

def myint2str(x, n):
    """
    Функция добавляет ведущие нули. Function padds integer x with zeros to n locations

    Usage:
     myint2str(x, n)

    Keyword arguments:
     x - integer
     n - number of locations
    """

    zzeros = '0'
    input_string = str(x)
    string_len = len(input_string)
    for zz in range(1,n-string_len,1):
        zzeros = zzeros + '0'

    rres = zzeros+str(x)
    return rres


def send_data(client, request, answer, error_message):
    request = request.encode()
    try:
        s.settimeout(5.0)
        s.send(request)
        data0 = s.recv(BUFFER_SIZE)
        data = data0.decode()
        if data != answer:
            msg = '{0}: {1}'.format(error_message, data)
            bagprint(msg, "LOG_ERR")
        else:
            if timer:
                timer.cancel()
            time.sleep(0.5)
            get_vent_status(client)
    except socket.error as error:
        msg = 'Network error: {0}'.format(error)
        bagprint(msg, "LOG_ERR")
        if vent_connect():
            send_data(client, request, answer, error_message)


def send_request(request):
    data = None
    try:
        s.settimeout(5.0)
        s.send(request.encode())
        data1 = s.recv(BUFFER_SIZE)
        data = (data1.decode())
    except socket.error as error:
        msg = 'Network error: {0}'.format(error)
        bagprint(msg, "LOG_ERR")
        if vent_connect():
            send_request(request)
    return data


def vent_connect():
    global s
    global running
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((TCP_IP, TCP_PORT))
        return True
    except socket.error as error:
        msg = 'Network error: {0}'.format(error)
        bagprint(msg, "LOG_ERR")
        running = False
    return False


def split_data(data, array_len=0):
    data_array = data.split('_')
    if len(data_array) != array_len:
        return None
    return data_array


def job():
    global subscribed_one_count
    bagprint("Sending mqtt autodiscovery...", "LOG_INFO")

    general_identifiers = "breezart"
    device_dict = {'identifiers': general_identifiers, 'name': 'Вентсистема', 'mf': 'Breezart', "hw_version": tpd_version, "sw_version": contr_version}
    # device_dict = {'device': {'identifiers': 'test1', 'name': 'Test1', 'mf': 'Breezart'}}

    arr_dict = {'device': device_dict, 'unique_id': general_identifiers}

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        # LocalBrocker.bag_pub("homeassistant/climate/thermostat_test1/config", payload, use_topic_header = False)
        pass
    
    speed_range = speed_max - speed_min + 1
    speed_list = []
    for speed_num in range(speed_range):
        speed_list.append(str(speed_num + 1))

    speeds_str = json.dumps(speed_list, ensure_ascii=False)

    device_small_dict = {'identifiers': general_identifiers}
    arr_dict = {
                "device": device_dict,
                "availability": {"topic": "breezart2/"},
                "unique_id": general_identifiers,
                "object_id": general_identifiers,
                "name": "Термостат",
                "temperature_command_topic": "breezart2/temp/target/set",   # Уставка температуры
                "temperature_state_topic":   "breezart2/temp/target/state", # Уставка температуры
                "current_temperature_topic": "breezart2/temp/current/state", # Текущая температура
                "mode_command_topic": "breezart2/mode/set",
                "mode_state_topic": "breezart2/mode/state",
                "modes": [ "off", "heat", "auto", "fan_only" ], 
                "fan_modes": speed_list,
                "fan_mode_state_topic": "breezart2/fanspeed/state",
                "fan_mode_command_topic": "breezart2/fanspeed/set",
                "temperature_unit": "C",
                "precision": 0.1,
                "temp_step": 1,
                "max_temp": temperature_max,
                "min_temp": temperature_min
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/climate/thermostat_test1/config", payload, use_topic_header = False)

    # Warning
    entity_identifiers = "breezart_warning"
    arr_dict = {
                "device": device_dict,
                "device_class": "problem",
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Warning",
                "icon": "mdi:alert-octagram-outline",
                "state_topic": "breezart2/Warning",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/Warning/config", payload, use_topic_header = False)

    # Critical
    entity_identifiers = "breezart_critical"
    arr_dict = {
                "device": device_dict,
                "device_class": "problem",
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Critical",
                "icon": "mdi:alert-octagram-outline",
                "state_topic": "breezart2/Critical",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/Critical/config", payload, use_topic_header = False)

    # Overheat
    entity_identifiers = "breezart_overheat"
    arr_dict = {
                "device": device_dict,
                "device_class": "problem",
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Overheat",
                "icon": "mdi:heat-wave",
                "state_topic": "breezart2/Overheat",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/Overheat/config", payload, use_topic_header = False)

    # AutoOff
    entity_identifiers = "breezart_autooff"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "AutoOff",
                "icon": "mdi:refresh-auto",
                "state_topic": "breezart2/AutoOff",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/AutoOff/config", payload, use_topic_header = False)

    # ChangeFilter
    entity_identifiers = "breezart_changefilter"
    arr_dict = {
                "device": device_dict,
                "device_class": "problem",
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "ChangeFilter",
                "icon": "mdi:air-filter",
                "state_topic": "breezart2/ChangeFilter",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/ChangeFilter/config", payload, use_topic_header = False)

    # Comfort
    entity_identifiers = "breezart_comfort"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Comfort",
                "state_topic": "breezart2/Comfort",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/Comfort/config", payload, use_topic_header = False)

    # is_power
    entity_identifiers = "breezart_is_power"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "is_power",
                "icon": "mdi:power",
                "state_topic": "breezart2/is_power",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/is_power/config", payload, use_topic_header = False)

    # is_powerblock
    entity_identifiers = "breezart_is_powerblock"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "is_powerblock",
                "icon": "mdi:block-helper",
                "state_topic": "breezart2/is_powerblock",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/is_powerblock/config", payload, use_topic_header = False)

    # SpeedIsDown
    entity_identifiers = "breezart_SpeedIsDown"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "SpeedIsDown",
                "icon": "mdi:fan-chevron-down",
                "state_topic": "breezart2/SpeedIsDown",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/SpeedIsDown/config", payload, use_topic_header = False)

    # is_regpressvav
    entity_identifiers = "breezart_is_regpressvav"
    arr_dict = {
                "device": device_dict,
                "device_class": None,
                "entity_category": "diagnostic",
                "availability": {"topic": "breezart2/"},
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Возможность рег давл в канале в режиме VAV",
                "icon": "mdi:arrow-collapse-vertical",
                "state_topic": "breezart2/is_regpressvav",
                "qos": 1
                }

    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/binary_sensor/is_regpressvav/config", payload, use_topic_header = False)

    # UnitState
    entity_identifiers = "breezart_UnitState"
    arr_dict = {
                "device": device_dict,
                "availability": {"topic": "breezart2/"},
                # "availability_mode": "all",
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "UnitState",
                "icon": "mdi:sign-real-estate",
                "state_topic": "breezart2/UnitState",
                "qos": 1
                }
    
    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/sensor/UnitState/config", payload, use_topic_header = False)

    # Unit_msg
    entity_identifiers = "breezart_Unit_msg"
    arr_dict = {
                "device": device_dict,
                "availability": {"topic": "breezart2/"},
                # "availability_mode": "all",
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Unit_msg",
                "icon": "mdi:message-outline",
                "state_topic": "breezart2/Unit_msg",
                "qos": 1
                }
    
    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/sensor/Unit_msg/config", payload, use_topic_header = False)

    # FilterDust
    entity_identifiers = "breezart_FilterDust"
    arr_dict = {
                "device": device_dict,
                "availability": {"topic": "breezart2/"},
                # "availability_mode": "all",
                "unique_id": entity_identifiers,
                "object_id": entity_identifiers,
                "name": "Загрязнённость фильтра",
                "icon": "mdi:weather-dust",
                "unit_of_measurement": "%",
                "state_topic": "breezart2/FilterDust",
                "qos": 1
                }
    
    payload = json.dumps(arr_dict, ensure_ascii=False)
    if LocalBrocker.connected_flag == True:
        LocalBrocker.bag_pub("homeassistant/sensor/FilterDust/config", payload, use_topic_header = False)



    for VAV_num, values in VZLs.items():
        device_identifiers = "brz_valve" + str(VAV_num)
        device_dict = {'identifiers': device_identifiers, 'name': 'Клапан ' + str(VAV_num), 'mf': 'Breezart', "via_device": general_identifiers}

        command_topic = LocalBrocker.BRtopic_header + "valves/" + str(VAV_num) + "/set"
        arr_dict = {
                    "device": device_dict,
                    "availability": {"topic": "breezart2/valves/" + str(VAV_num) + "/availability", "topic": "breezart2/"},
                    "availability_mode": "all",
                    "unique_id": device_identifiers,
                    "object_id": device_identifiers,
                    "name": "Клапан " + str(VAV_num),
                    "icon": "mdi:valve",
                    "command_topic": command_topic,
                    "state_topic": "breezart2/valves/" + str(VAV_num) + "/LevelFact",
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "unit_of_measurement": "%",
                    "qos": 1
                    }
        
        payload = json.dumps(arr_dict, ensure_ascii=False)
        if LocalBrocker.connected_flag == True:
            if (subscribed_one_count == False):
                LocalBrocker.bag_subscribe(command_topic, use_topic_header = False)
            LocalBrocker.bag_pub("homeassistant/number/valve" + str(VAV_num) + "/config", payload, use_topic_header = False)
            
            
        entity_identifiers = "brz_valve_status" + str(VAV_num)

        arr_dict = {
                    "device": device_dict,
                    "availability": {"topic": "breezart2/"},
                    # "availability_mode": "all",
                    "unique_id": entity_identifiers,
                    "object_id": entity_identifiers,
                    "name": "Status",
                    "icon": "mdi:valve",
                    "state_topic": "breezart2/valves/" + str(VAV_num) + "/StateV",
                    "qos": 1
                    }
        
        payload = json.dumps(arr_dict, ensure_ascii=False)
        if LocalBrocker.connected_flag == True:
            LocalBrocker.bag_pub("homeassistant/sensor/valve" + str(VAV_num) + "/config", payload, use_topic_header = False)



MQTTtopic_header = "breezart2/"
subscribe_to_topics = ["mode/set", "temp/target/set", "fanspeed/set"]
LWT_topic = MQTTtopic_header

LocalBrocker = LocalBrocker_on_message(client_id=ProgrammName)
mqtt_cred_name="LocalBrocker"
if mqtt_cred_name not in mqtt_credentials_from_file_dict:
    msg = "Error: Credential for '" + mqtt_cred_name + "' does not exist in the file '" + mqtt_credential_file_path + "'"
    bagprint(msg, "LOG_ERR")

LocalBrocker.setPlaces(
    name=mqtt_cred_name,
    host=mqtt_credentials_from_file_dict.get(mqtt_cred_name).get("host"),
    port=int(mqtt_credentials_from_file_dict.get(mqtt_cred_name).get("port")),
    user=mqtt_credentials_from_file_dict.get(mqtt_cred_name).get("user"),
    password=mqtt_credentials_from_file_dict.get(mqtt_cred_name).get("password"),
    topic_header=MQTTtopic_header,
    subscribe_to_topics = subscribe_to_topics,
    will_set_topic = "",
    ProgrammName = ProgrammName,
    DEBUG_PROTOCOL = False,
    DEBUG_MQTT = DEBUG_MQTT,
    DEBUG_PRINT = DEBUG_PRINT,
    )

LocalBrocker.BRinfo()
LocalBrocker.run2()



if __name__ == '__main__':
# with daemon.DaemonContext():
    msg = 'Bridge BREEZARD-MQTT started'
    bagprint(msg, "LOG_INFO")

    job()
    schedule.every(10).seconds.do(job)
    # schedule.every(1).minutes.do(job)

    # noinspection PyBroadException
    try:
        vent_connect()
        if not check_vent_params():
            raise Exception

        mqtt_client = mqtt.Client(CLIENT_ID, True if CLIENT_ID else False)
        mqtt_client.will_set(PREFIX + '/LWT', 'Offline', 0, True)
        mqtt_client.on_connect = on_connect_mqtt
        mqtt_client.on_message = on_message
        mqtt_client.username_pw_set(USERNAME, PASSWORD)
        mqtt_client.connect(BROKER, 1883, 60)

        mqtt_client.loop_start()
        get_vent_status(mqtt_client)

        # infinite loop ...
        while running:
            time.sleep(0.1)
            schedule.run_pending()

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error_string:
        msg = 'Bridge have error'
        bagprint(msg, "LOG_ERR")
        msg = error_string
        bagprint(msg, "LOG_ERR")
        sys.exit(-1)
    finally:
        if s:
            s.close()
        if timer:
            timer.cancel()
        msg = 'Bridge terminated'
        bagprint(msg, "LOG_INFO")
