from zmq import device
import ujson as json
from lib.mqtt_as import MQTTClient
import network
from ubinascii import hexlify
import machine

class Device(dict):
    def __init__(self, name: bytes, model: bytes, manufacturer: bytes):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        macaddr = hexlify(wlan.config('mac'), ':')

        super().__init__(
            name=name,
            model=model,
            manufacturer=manufacturer,
            identifiers=hexlify(machine.unique_id()),
            connections= [
                [
                    "mac",
                    macaddr
                ]
            ],
        )

class BaseEntity(object):
    def __init__(
        self,
        mqtt: MQTTClient,
        name: bytes,
        component: bytes,
        object_id: bytes,
        node_id = None,
        discovery_prefix = b'homeassistant',
        device = None,
        extra_conf = None
    ):
        self.mqtt = mqtt

        base_topic = discovery_prefix + b'/' + component # type: ignore
        if node_id:
            base_topic += b'/' + node_id
        base_topic += b'/' + object_id # type: ignore

        self.config_topic = base_topic + b'/config'
        self.state_topic = base_topic + b'/state'

        self.config = {
            "name": name,
            "stat_t": b'~/state',
            "~": base_topic
        }

        if device:
            self.config['device'] = device

        if extra_conf:
            self.config.update(extra_conf)

        _ = self.mqtt.publish(self.config_topic, bytes(json.dumps(self.config), 'utf-8'), True, 1)

    async def remove_entity(self):
        await self.mqtt.publish(self.config_topic, b'', qos=1)

    async def publish_state(self, state):
        await self.mqtt.publish(self.state_topic, state)

    @property
    def base_topic(self):
        return self.config['~']

class BinarySensor(BaseEntity):
    def __init__(
        self,
        mqtt: MQTTClient,
        name,
        object_id,
        device = None,
        node_id=None,
        discovery_prefix=b'homeassistant',
        extra_conf=None
    ):
        super().__init__(
            mqtt=mqtt,
            name=name,
            component=b'binary_sensor',
            device=device,
            object_id=object_id,
            node_id=node_id,
            discovery_prefix = discovery_prefix,
            extra_conf=extra_conf
        )

    async def publish_state(self, state):
        await self.mqtt.publish(self.state_topic, b'ON' if state else b'OFF')

    async def on(self):
        await self.publish_state(True)

    async def off(self):
        await self.publish_state(False)

class Sensor(BaseEntity):
    def __init__(
        self,
        mqtt: MQTTClient,
        name,
        object_id,
        node_id=None,
        discovery_prefix=b'homeassistant',
        extra_conf=None
    ):
        super().__init__(
            mqtt=mqtt,
            name=name,
            component=b'sensor',
            device=device,
            object_id=object_id,
            node_id=node_id,
            discovery_prefix=discovery_prefix,
            extra_conf=extra_conf,
        )

class EntityGroup(object):
    def __init__(self, mqtt: MQTTClient, node_id, discovery_prefix=b'homeassistant', extra_conf=None):
        self.mqtt = mqtt
        self.node_id = node_id
        self.discovery_prefix = discovery_prefix
        # Group wide extra conf, gets passed to sensors
        self.extra_conf = extra_conf
        # Read state_topic from config if provided
        if "state_topic" in extra_conf:
            self.state_topic = extra_conf["state_topic"]
        else:
            self.state_topic = discovery_prefix + b'/sensor/' + node_id + b'/state'
            extra_conf["state_topic"] = self.state_topic
        self.entities = []

    def _update_extra_conf(self, extra_conf):
        if "value_template" not in extra_conf:
            raise Exception("Groupped sensors need value_template to be set.")

        extra_conf.update(self.extra_conf)

    def create_binary_sensor(self, name, object_id, extra_conf):
        self._update_extra_conf(extra_conf)
        bs = BinarySensor(self.mqtt, name, object_id, self.node_id,
                self.discovery_prefix, extra_conf)
        self.entities.append(bs)
        return bs

    def create_sensor(self, name, object_id, extra_conf):
        self._update_extra_conf(extra_conf)
        s = Sensor(self.mqtt, name, object_id, self.node_id,
                self.discovery_prefix, extra_conf)
        self.entities.append(s)
        return s

    async def publish_state(self, state):
        await self.mqtt.publish(self.state_topic, bytes(json.dumps(state), 'utf-8'))

    async def remove_group(self):
        for e in self.entities:
            await e.remove_entity()


