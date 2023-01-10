import digitalio


class RXTXSwitch:
    def __init__(self, switch_pin, rx_led_pin, tx_led_pin, tx_value=True):

        self.switch = digitalio.DigitalInOut(switch_pin)
        self.rx_led = digitalio.DigitalInOut(rx_led_pin)
        self.tx_led = digitalio.DigitalInOut(tx_led_pin)
        self.tx_value = tx_value

    def transmit(self):
        """
        Enable TX mode
        """
        self.switch.value = self.tx_value
        self.tx_led.value = True
        self.rx_led.value = False

    def receive(self):
        """
        Enable RX mode
        """
        self.switch.value = not self.tx_value
        self.tx_led.value = False
        self.rx_led.value = True

    def idle(self):
        """
        Enable idle
        """
        self.switch.value = not self.tx_value
        self.tx_led.value = False
        self.rx_led.value = False
