import ujson as json
from .lib.mqtt_as import MQTTClient
import network
from ubinascii import hexlify
import machine

class Device:
    payload_available = b'1'
    payload_unavailable = b'0'

    def __init__(
        self,
        mqtt: MQTTClient,
        name: bytes,
        model: bytes,
        manufacturer: bytes,
        device_id: bytes,
        discovery_prefix = b'homeassistant',
     ):
        avail_t_suffix = b'avail'
        hardwareId = hexlify(machine.unique_id())

        self.device_id = device_id
        self.mqtt = mqtt
        self.avail_topic = discovery_prefix + b'/' + device_id + b'-' + hardwareId + b'/' + avail_t_suffix


        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        macaddr = hexlify(wlan.config('mac'), ':')

        self.mqtt.set_last_will(self.avail_topic, self.payload_unavailable, qos=1)

        self.config = {
            'device': {
                'name': name,
                'model': model,
                'manufacturer': manufacturer,
                'identifiers': hexlify(machine.unique_id()),
                'connections':  [
                    [
                        "mac",
                        macaddr
                    ]
                ],
            },
            'availability': {
                'payload_available': self.payload_available,
                'payload_not_available': self.payload_unavailable,
                'topic': self.avail_topic
            },
        }

    async def init_mqtt(self):
        await self.mqtt.subscribe(b'homeassistant/status')
        await self._publish_available()

    async def _publish_available(self):
        await self.mqtt.publish(self.avail_topic, self.payload_available)

    async def handle_mqtt_message(self, topic: bytes, message):
        if topic == b'homeassistant/status' and message == b'online':
            await self._handle_ha_start()

    async def _handle_ha_start(self):
        await self._publish_available()

class BaseEntity(object):
    def __init__(
        self,
        mqtt: MQTTClient,
        name: bytes,
        component: bytes,
        device: Device,
        unique_id = None,
        object_id = None,
        node_id = None,
        discovery_prefix = b'homeassistant',
        extra_conf = None,
        # 'config', 'diagnostic' or None
        entity_category = None,
        icon = None
    ):

        self.mqtt = mqtt

        base_topic = discovery_prefix + b'/' + component # type: ignore
        if node_id:
            base_topic += b'/' + node_id

        hardwareId = hexlify(machine.unique_id())

        object_id = (object_id if object_id else component) + b'-' + hardwareId

        base_topic += b'/' + object_id

        self.config_topic = base_topic + b'/config'
        self.state_topic = base_topic + b'/state'

        self.config = {
            "name": name,
            "stat_t": b'~/state',
            "~": base_topic,
            'uniq_id': unique_id if unique_id else object_id,
        }

        if entity_category:
            self.config['entity_category'] = entity_category

        if icon:
            self.config['icon'] = icon

        if extra_conf:
            self.config.update(extra_conf)

        self.config.update(device.config)

    async def init_mqtt(self):
        await self.mqtt.publish(self.config_topic, bytes(json.dumps(self.config), 'utf-8'), False, 1)

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
        device: Device,
        object_id = None,
        node_id=None,
        unique_id=None,
        # see https://www.home-assistant.io/integrations/binary_sensor/#device-class
        device_class=None,
        discovery_prefix=b'homeassistant',
        entity_category = None,
        extra_conf=None,
        icon = None,
    ):
        config = {}

        if device_class:
            config['device_class'] = device_class

        if extra_conf:
            config.update(extra_conf)

        super().__init__(
            mqtt=mqtt,
            name=name,
            component=b'binary_sensor',
            device=device,
            object_id=object_id,
            unique_id=unique_id,
            node_id=node_id,
            discovery_prefix = discovery_prefix,
            extra_conf=config,
            entity_category=entity_category,
            icon=icon,
        )

    async def init_mqtt(self):
        await super().init_mqtt()
        await self.publish_state(False)

    async def publish_state(self, state: bool):
        await self.mqtt.publish(self.state_topic, b'ON' if state else b'OFF')

    async def on(self):
        await self.publish_state(True)

    async def off(self):
        await self.publish_state(False)

class Sensor(BaseEntity):
    def __init__(
        self,
        mqtt: MQTTClient,
        name: bytes,
        object_id: bytes,
        device: Device,
        node_id=None,
        discovery_prefix=b'homeassistant',
        state_class=None,
        extra_conf=None,
        icon=None,
        entity_category=None,
    ):
        config = extra_conf if extra_conf else {}

        if state_class:
            config['state_class'] = state_class

        super().__init__(
            mqtt=mqtt,
            name=name,
            component=b'sensor',
            device=device,
            object_id=object_id,
            node_id=node_id,
            discovery_prefix=discovery_prefix,
            extra_conf=config,
            icon=icon,
            entity_category=entity_category,
        )
