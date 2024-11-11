import serial
from registers import *
import logging
import time
# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Change to logging.INFO or logging.ERROR as needed
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()  # Output to console
        # To log to a file, add: logging.FileHandler("sensor_log.txt")
    ]
)

class Xensiv:
    def __init__(self, port = "/dev/tty.usbmodem114101", baud_rate = 9600):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1  # Timeout in seconds
        )
        if self.ser.is_open:
            logging.info(f"Sensor connection ESTABLISHED at {port}!")
        else:
            logging.error(f"FAILED connection with sensor at {port}")

        self.reg_reset()        # Reset the sensor

    def get_binary(self, data):
        """Converts the received data to binary."""
        int_val = int(data[-2:],16)
        binary = bin(int_val)
        #logging.info(f"Binary value of {data} is {binary[2:]}")
        return binary[2:]

    def check_ack(self) -> None:
        """Checks if the received data is an ACK or NACK after write operation."""
        data = self.receive_data()
        if data == ACK:
            logging.debug("Received ACK.")
        elif data == NACK:
            logging.debug("Received NACK.")
        else:
            logging.debug(f"ACK/NACK failed with: {data}")

    def receive_data(self) -> bytes:
        """Reads the UART port and returns the data received."""
        if self.ser.is_open:
            data = self.ser.readline()
            data = data.replace(b'\n', b'')  # remove \n at the end
            if data != ACK and data != NACK and data != b'\x00':
                logging.debug(f"Received: {data}: {self.get_binary(data)}")
                self.get_binary(data)
        else:
            logging.error("UART connection is closed.")
        return data

    def send_data(self, data) -> None:
        """Sends data to the UART port."""
        logging.debug(f"Sent: {data}")
        if self.ser.is_open:
            self.ser.write(data)
            time.sleep(0.1)
            if data[:1] == write:  # If writing data, expect an ACK/NACK (:1 instead of 0 to get it as bytearray)
                self.check_ack()
        else:
            logging.debug("Sending data failed, connection closed.")

    def reg_product_id(self) -> None:
        """Reads the product ID register."""
        logging.debug("Reading the product ID register.")
        self.send_data(read + reg_prod_id + end_message)
        time.sleep(0.1)
        data_received = self.receive_data()

    def reg_sensor_sts(self) -> None:
        """Reads the sensor status register."""
        logging.debug("Reading the sensor status register.")
        self.send_data(read + reg_sens_sts + end_message)
        time.sleep(0.1)
        data_received = self.receive_data()

    def reg_meas_rate(self, access) -> None:
        """Reads/write the measurement rate register."""
        logging.debug("Reading/writing the measurement rate register.")
        if access == "read":
            self.send_data(read + reg_meas_rate_h + end_message)
            time.sleep(0.1)
            data_received = self.receive_data()
            time.sleep(0.1)
            self.send_data(read + reg_meas_rate_l + end_message)
            time.sleep(0.1)
            data_received = self.receive_data()
        if access == "write":
            self.reg_meas_config()
            time.sleep(0.1)
            self.send_data(write + reg_meas_conf + idle_mode + end_message) # need transition from idle to continuous mode, see registermap description
            time.sleep(0.1)
            self.reg_meas_config()
            time.sleep(0.1)

            self.send_data(write + reg_meas_rate_h + b'\x2C00' + end_message)
            time.sleep(0.1)
            self.send_data(write + reg_meas_rate_l + b'\x2C05' + end_message) # i guess 5 is minimum, value = seconds per sample
            time.sleep(0.1)
        return

    def reg_meas_config(self) -> None:
        """Reads the measurement configuration register."""
        logging.debug("Reading the measurement configuration register.")
        self.send_data(read + reg_meas_conf + end_message)
        time.sleep(0.1)
        data_received = self.receive_data()

    def reg_reset(self) -> None:
        """Resets the sensor."""
        logging.info("Resetting the sensor.")
        self.send_data(write + reg_soft_reset + soft_rest + end_message)
        return

    def continuous_read(self) -> None:
        """Reads the sensor continuously."""
        self.reg_meas_rate("write")
        # Set the measurement configuration to continuous mode
        self.send_data(write + reg_meas_conf + continuous_mode + end_message)
        time.sleep(0.1)

        while True:
            self.send_data(read + reg_co2ppm_h + end_message)
            time.sleep(0.1)
            bits_h = self.receive_data()
            time.sleep(0.1)
            self.send_data(read + reg_co2ppm_l + end_message)
            time.sleep(0.1)
            bits_l = self.receive_data()
            time.sleep(0.1)
            # Convert the data to integer
            integer_val_h = int(bits_h, 16)
            integer_val_l = int(bits_l, 16)
            # Combine the high and low bytes
            integer_val = (integer_val_h << 8) | integer_val_l
            logging.info(f"CO2: {integer_val} ppm")
            time.sleep(4.4)         # 4.4 seconds per sample (5 seconds per sample (highest) - 0.6 seconds for the sensor to process the data)


sens = Xensiv()
sens.continuous_read()