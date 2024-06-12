import paho.mqtt.client as mqtt
from subprocess import call

class BagMQTTClass(mqtt.Client):
    rc_txt = {
        0: "Connection successful",
        1: "Connection refused - incorrect protocol version",
        2: "Connection refused - invalid client identifier",
        3: "Connection refused - server unavailable",
        4: "Connection refused - bad username or password",
        5: "Connection refused - not authorised"
    }

    def setPlaces(self, name, host, port, user, password, topic_header, subscribe_to_topics, will_set_topic, ProgrammName, DEBUG_PROTOCOL, DEBUG_MQTT, DEBUG_PRINT):
        self.BRname = name
        self.BRhost = str(host)
        self.BRport = int(port)
        self.BRuser = str(user)
        self.BRpassword = str(password)
        self.BRclient_id = str(self._client_id)
        self.BRtopic_header = str(topic_header)
        self.subscribe_to_topics = subscribe_to_topics
        self.connected_flag = False
        self.will_set_topic = will_set_topic
        self.ProgrammName = ProgrammName
        self.DEBUG_PROTOCOL = DEBUG_PROTOCOL
        self.DEBUG_MQTT = DEBUG_MQTT
        self.DEBUG_PRINT = DEBUG_PRINT

    def tologread(self, msg):
        call(["logger", "-t", self.ProgrammName, msg])
        if self.DEBUG_PRINT: print(msg)

    def BRinfo(self):
        self.tologread ("Connection data: {} ({}:{}), u={}, pass={}, client_id={}, topic_header={}, topic={}".format(self.BRname, self.BRhost, self.BRport, self.BRuser, self.BRpassword, self.BRclient_id, self.BRtopic_header, self.subscribe_to_topics))
        pass

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.connected_flag = False
            msg="Unexpected disconnection"
            self.tologread(msg)
            # tozabbix("mqtt_disconnect", "1")

    def bag_subscribe(self, topic, use_topic_header = True):
        if use_topic_header == True:
            topic2 = self.BRtopic_header + topic
        else:
            topic2 = topic
        res = self.subscribe(topic2)
        # if res == mqtt.MQTT_ERR_SUCCESS:
        #     self.tologread("Successfully subscribed to topic: " + topic2)
        #     # tozabbix("mqtt_disconnect", "0")
        #     self.publish(self.BRtopic_header + self.will_set_topic, "online", qos=0, retain=True)
        # else:
        #     msg="Error! Client is not subscribed to topic " + topic2
        #     self.tologread(msg)
        #     # tozabbix("mqtt_disconnect", "1")

    def on_connect(self, mqttc, obj, flags, rc):
        if rc == 0:
            self.tologread("Brocker=" + self.BRname + ", rc: " + str(rc) + " (" + self.rc_txt[rc] + ")")
            self.connected_flag=True

            for subscribe_to_topic in self.subscribe_to_topics:
                subscribe_to_topic = self.BRtopic_header + subscribe_to_topic
                res = self.subscribe(subscribe_to_topic)
                if rc == mqtt.MQTT_ERR_SUCCESS:
                    self.tologread("Successfully subscribed to topic: " + subscribe_to_topic)
                    # tozabbix("mqtt_disconnect", "0")
                    self.publish(self.BRtopic_header + self.will_set_topic, "online", qos=0, retain=True)
                else:
                    msg="Error! Client is not subscribed to topic " + subscribe_to_topic
                    self.tologread(msg)
                    # tozabbix("mqtt_disconnect", "1")
        else:
            self.connected_flag = False
            # tozabbix("mqtt_disconnect", "1")
            msg="Unexpected disconnection"
            self.tologread(msg)


    def on_message(self, mqttc, obj, msg):
        self.tologread("Brocker=" + self.BRname + ". Recieved msg: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        self.tologread("Brocker=" + self.BRname + ", subscribed: mid=" + str(mid) + ", granted_qos=" + str(granted_qos))

    def on_log(self, mqttc, obj, level, string):
        pass

    def bag_pub(self, topic, payload, retain = False, use_topic_header = True): 
        if (self.connected_flag == True):
            if use_topic_header == True:
                topic2 = self.BRtopic_header + topic
            else:
                topic2 = topic


            (rc, mid) = self.publish(topic2, payload, retain = retain)
            if (rc != 0):
                self.connected_flag = False
                msg="Error to send mqtt. rc=" + str(rc) + ". " + str(self.rc_txt[rc]) + ". mid=" + str(mid)
                self.tologread(msg)
                # tozabbix("mqtt_pub_err", str(rc) + ": " + str(self.rc_txt[rc]))
            else:
                if (self.DEBUG_MQTT):
                    self.tologread ("Success send mqtt: {}, t={}, msg={}".format(self.BRname, topic2, payload))
        else:
            self.tologread ("Scipped trying send mqtt because connected_flag = False")

    def run2(self):
        self.username_pw_set(username=self.BRuser,password=self.BRpassword)

        try:
            self.tologread(self.BRtopic_header)
            self.will_set(self.BRtopic_header + self.will_set_topic, 'offline', 0, False)
            self.connect(self.BRhost, self.BRport, 60)
        except Exception as error_string:
            msg="Error to connect mqtt. Broker={}. Error: {}".format(self.BRname, str(error_string))
            self.tologread(msg)
            # tozabbix("mqtt_connect_error", 1)
            pass
        else:
            # tozabbix("mqtt_connect_error", "0")
            pass

        self.loop_start()

    def exit(self):
        self.disconnect()
        self.loop_stop()
