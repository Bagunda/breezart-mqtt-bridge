# breezart-mqtt
Сервис-мост между интерфейсом вентиляции Breezart с клапанами и брокером MQTT для систем умного дома (MajorDoMo, Domoticz, OpenHAB 2, Home Assistant и т.д.)
Программа обладает функцией MQTT AutoDiscovery. Это значит, что все сущности автоматически попадут в Home Assistant и сразу будут настроены нужным образом. В Home Assistant вообще ничего не надо настраивать, кроме как поднять брокера и добавить MQTT клиента. И автообнаружение само отработает как надо.

Диденко Александр. [+79802616369](tel:+79802616369), [wa.me/+79802616369](https://wa.me/+79802616369), [t.me/+79802616369](https://t.me/+79802616369), [vk.com/Bagunda](https://vk.com/Bagunda). Обращайтесь если нужно что-то сделать по этой теме на коммерческой основе. Сам я УмноДомщик с громадным стажем. Могу связать всё со всем.

Этот вид связи Breezart с Home Assistant доступен только есил сперва установлен Линукс и потом на этот этот Линукс установлен Home Assistant Supervised. Этот метод не возможно реализовать при типе установке HAOS. HAOS - это вообще для домохозяек. Рекомендую не выбирать такой вид Home Assistant.
Постараюсь разработать этот драйвер чтобы можно было им пользоваться из HAOS. Но наверно смогу это сделать не раньше чем 03.2025.

## Запуск сервиса

1. `apt install python3-paho-mqtt`
3. `apt install python3-schedule`
4. Скопируем файл bag_breezart-mqtt.py в папку /root/diy/breezart/
5. Скопируем файл BagMQTTClass.py в папку /root/diy/
6. Скопируем файл mqtt_credentials.json в папку /root/diy/
7. Отредактируем параметры подключения в заголовке файла:
- адрес пульта вентиляции в TCP_IP
- активируем пароль в настройках пульта и пропишем в TCP_PASS
3. Настроим подключение к брокеру MQTT - адрес, логин и пароль в файле /root/diy/mqtt_credentials.json
4. Настроим запуск сервиса в автоматическом режиме с использованием systemd
- введём команду `systemctl edit --force --full breezart-mqtt.service` и вставим туда содержимое:

```
[Unit]
Description=Breezart-MQTT GateWay with Home Assistant autodiscovery
After=multi-user.target

[Service]
Type=idle
ExecStart=/usr/bin/python3 /root/diy/breezart/bag_breezart-mqtt.py
Restart=always

[Install]
WantedBy=multi-user.target
```

- Перезапустим systemd, добавим и запустим наш сервис:

```
systemctl daemon-reload
systemctl enable breezart-mqtt.service
systemctl start breezart-mqtt.service
```

## MQTT Топики для получения состояния и посыла команд

```
breezart2/#
```


## MQTT Топики для посыла команд

```
breezart2/valves/VAV_num/set - VAV_num - номер клапана по порядку его определения вентустановкой. Количество клапанов определяется автоматически. И правильное количество клапанов правильно залетает в Home Assistance (autodiscovery)
breezart2/mode/set - установка режима: HEAT, COOL, AUTO, FAN_ONLY, OFF (большие буквы не обязательны)
breezart2/temp/target/set - установка уставки температуры
breezart2/fanspeed/set - установка уставки скорости работы вентилятора. Количество скоростей определяется автоматически путём опроса контроллера (пульт)
```

## Контроль работы

Сообщения о работе сервиса записываются в системный журнал (`journalctl -f`)
MQTT сообщения можно читать такой командой:
```
mosquitto_sub -h 192.168.0.126 -t "#" -v -u "mqtt_login" -P "mqtt_pass"
```


## Известные проблемы

- недостаточно оттестировано
- структура кода - так себе, пока что принцип "работает - да и ладно"
- не реализовано получение настроек сценариев
- начинаю изучать классы, поэтому существует файл BagMQTTClass.py, который по большому счёту не стоило бы делать, но мне проще было сделать именно такую связку

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/93df6847-0728-490a-9f85-53cf6f44fa83)

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/84616ebc-def4-4626-9fdc-b93b70a63b8f)

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/b70384fe-9c0f-4f0e-a1f5-b3dfcb76499a)

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/893b85c6-20a5-493f-8af6-6ffc3066d4b4)

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/a76a0fe4-2d97-4b6f-845f-55bb407276d7)

![image](https://github.com/Bagunda/breezart-mqtt-bridge/assets/16766521/94563d1a-3524-4402-9f3b-d946047fff29)










