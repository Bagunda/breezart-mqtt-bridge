# breezart-mqtt
Сервис-мост между интерфейсом вентиляции Breezart с клапанами и брокером MQTT для систем умного дома (MajorDoMo, Domoticz, OpenHAB 2, Home Assistant и т.д.)
Программа обладает функцией MQTT AutoDiscovery. Это значит, что все сущности автоматически попадут в Home Assistant и сразу будут настроены нужным образом. В Home Assistant вообще ничего не надо настраивать, кроме как поднять брокера и добавить MQTT клиента. И автообнаружение само отработает как надо.

## Запуск сервиса

1. Скопируем файл bag_breezart-mqtt.py в папку /root/diy/breezart/
2. Скопируем файл BagMQTTClass.py в папку /root/diy/
3. Скопируем файл mqtt_credentials.json в папку /root/diy/
4. Отредактируем параметры подключения в заголовке файла:
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

## MQTT Топики для получения состояния

```
breezart/#
```

## Контроль работы

Сообщения о работе сервиса записываются в системный журнал (`journalctl -f`)

## Известные проблемы

- недостаточно оттестировано
- структура кода - так себе, пока что принцип "работает - да и ладно"
- не реализовано получение настроек сценариев
- начинаю изучать классы, поэтому существует файл BagMQTTClass.py, который по большому счёту не стоило бы делать, но мне проще было сделать именно такую связку
