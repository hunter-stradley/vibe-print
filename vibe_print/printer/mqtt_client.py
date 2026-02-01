"""
MQTT Client - Low-level MQTT communication with compatible FDM printers.

Handles secure MQTT connection, authentication, and message exchange.
"""

import asyncio
import json
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable
import paho.mqtt.client as mqtt

from vibe_print.config import config


@dataclass
class MQTTConfig:
    """MQTT connection configuration."""
    host: str
    port: int = 8883  # TLS port
    access_code: str = ""
    serial_number: str = ""
    username: str = "bblp"  # Default username for compatible printers
    use_tls: bool = True


class PrinterMQTTClient:
    """
    Low-level MQTT client for FDM printer communication.

    Handles connection, authentication, and message routing.
    """

    # MQTT Topics for compatible printers
    TOPIC_REPORT = "device/{serial}/report"
    TOPIC_REQUEST = "device/{serial}/request"

    def __init__(
        self,
        host: Optional[str] = None,
        access_code: Optional[str] = None,
        serial_number: Optional[str] = None,
    ):
        """
        Initialize MQTT client.

        Args:
            host: Printer IP address
            access_code: Printer access code
            serial_number: Printer serial number
        """
        self.config = MQTTConfig(
            host=host or config.printer.ip_address,
            access_code=access_code or config.printer.access_code,
            serial_number=serial_number or config.printer.serial_number,
        )

        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._message_callbacks: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self._last_report: Optional[Dict[str, Any]] = None
        self._sequence_id = 0

    @property
    def is_connected(self) -> bool:
        """Check if connected to printer."""
        return self._connected

    @property
    def report_topic(self) -> str:
        """Get the report topic for this printer."""
        return self.TOPIC_REPORT.format(serial=self.config.serial_number)

    @property
    def request_topic(self) -> str:
        """Get the request topic for this printer."""
        return self.TOPIC_REQUEST.format(serial=self.config.serial_number)

    def _get_next_sequence_id(self) -> str:
        """Get next sequence ID for requests."""
        self._sequence_id += 1
        return str(self._sequence_id)

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the printer via MQTT.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        if not self.config.host or not self.config.access_code:
            raise ValueError(
                "Printer IP and access code required. "
                "Set VIBE_PRINTER_IP and VIBE_ACCESS_CODE environment variables."
            )

        # Create MQTT client
        client_id = f"vibe-print-{int(time.time())}"
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # Set credentials
        self._client.username_pw_set(
            self.config.username,
            self.config.access_code,
        )

        # Configure TLS
        if self.config.use_tls:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self._client.tls_set_context(ssl_context)

        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Connect
        try:
            self._client.connect_async(
                self.config.host,
                self.config.port,
                keepalive=60,
            )
            self._client.loop_start()

            # Wait for connection
            start_time = time.time()
            while not self._connected and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.1)

            if not self._connected:
                self._client.loop_stop()
                return False

            # Subscribe to report topic
            self._client.subscribe(self.report_topic)
            return True

        except Exception as e:
            print(f"MQTT connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from printer."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection callback."""
        if rc == 0:
            self._connected = True
        else:
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password (check access code)",
                5: "Not authorized",
            }
            print(f"MQTT connection failed: {error_messages.get(rc, f'Unknown error {rc}')}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Handle MQTT disconnection callback."""
        self._connected = False

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(message.payload.decode())
            self._last_report = payload

            # Call registered callbacks
            for callback in self._message_callbacks.values():
                asyncio.create_task(callback(payload))

        except json.JSONDecodeError:
            pass

    def register_callback(
        self,
        name: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register a callback for incoming messages."""
        self._message_callbacks[name] = callback

    def unregister_callback(self, name: str) -> None:
        """Unregister a message callback."""
        self._message_callbacks.pop(name, None)

    async def send_command(
        self,
        command_type: str,
        command: str,
        **kwargs,
    ) -> bool:
        """
        Send a command to the printer.

        Args:
            command_type: Type of command (e.g., "print", "system")
            command: Command name
            **kwargs: Additional command parameters

        Returns:
            True if command was sent
        """
        if not self._connected or not self._client:
            raise ConnectionError("Not connected to printer")

        payload = {
            command_type: {
                "sequence_id": self._get_next_sequence_id(),
                "command": command,
                **kwargs,
            }
        }

        self._client.publish(
            self.request_topic,
            json.dumps(payload),
            qos=1,
        )
        return True

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Request and return current printer status.

        Returns:
            Status dictionary or None if not available
        """
        if not self._connected:
            return None

        # Send status request
        await self.send_command("pushing", "pushall")

        # Wait briefly for response
        await asyncio.sleep(0.5)

        return self._last_report

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        """Get the most recent status report."""
        return self._last_report


# Backwards compatibility alias
BambuMQTTClient = PrinterMQTTClient


# Convenience function to test connection
async def test_printer_connection(
    host: str,
    access_code: str,
    serial_number: str,
) -> tuple[bool, str]:
    """
    Test connection to a compatible FDM printer.

    Returns:
        Tuple of (success, message)
    """
    client = PrinterMQTTClient(
        host=host,
        access_code=access_code,
        serial_number=serial_number,
    )

    try:
        connected = await client.connect(timeout=5.0)
        if connected:
            status = await client.get_status()
            await client.disconnect()

            if status:
                return True, f"Connected successfully. Printer status available."
            return True, "Connected but no status received."

        return False, "Connection timed out. Check IP address and access code."

    except Exception as e:
        return False, f"Connection error: {e}"
