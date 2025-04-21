import time

import can
import cantools


class CanifListener(can.Listener):
    """
    Listens for CAN messages, decodes them using a CAN database, and updates
    a shared dictionary with the extracted signal values. The CanGui class
    uses tkinter and therefore must run in the main process and cannot handle
    threads. This listener can be added to a can.Notifier before launching
    the GUI.

    Inherits from the `can.Listener` class, which defines the interface
    for receiving messages from a CAN bus.
    """

    def __init__(
        self,
        sig_vals: dict,
        database: cantools.database.can.Database,
        rx_msg_stats: dict,
    ):
        """
        Initialize CanGuiListener instance.

        Args:
            sig_vals (dict):
                A dictionary to store the received signal values.
                The structure is expected to be:
                {message_name: {signal_name: signal_value, ...}, ...}.
            database (cantools.database.can.Database):
                The cantools database object containing the CAN message
                and signal definitions.
            rx_msg_stats (dict):
                {msg_name: {'last_received': timestamp, 'cycle_time': timestamp, 'count': timestamp}}
        """
        self.sig_vals: dict = sig_vals
        self.db: cantools.database.can.Database = database
        self.rx_msg_stats: dict = rx_msg_stats

    def on_error(self, exc: Exception) -> None:
        """
        Handle CAN bus errors.

        This method is called by the can.Notifier instance when an error
        frame is received. It prints the error and raises the exception.

        Args:
            exc (Exception): The exception representing the error.
        """
        print(f"Listener: {repr(exc)}")
        raise exc

    def on_message_received(self, msg: can.Message) -> None:
        """
        Process received CAN messages.

        This method is called by the can.Notifier instance when a new
        CAN message is received. It decodes the message and updates
        the signal values in the `self.sig_vals` dictionary.

        Args:
            msg (can.Message): The received CAN message.
        """
        msg_id = msg.arbitration_id
        try:
            rx_msg = self.db.get_message_by_frame_id(msg_id)
            rx_vals = rx_msg.decode(msg.data, decode_choices=False)
            # update main dictionary
            for signal in rx_msg.signals:
                self.sig_vals[rx_msg.name][signal.name] = rx_vals[signal.name]

            if self.rx_msg_stats:
                now = time.time()
                milliseconds = int(round(now * 1000) % 1000)
                timestamp = time.strftime("%H:%M:%S.") + str(milliseconds).zfill(3)
                data = self.rx_msg_stats[rx_msg.name]
                prev_ts = data["prev_ts"]
                data["last_received"] = timestamp
                data["cycle_time"] = round(now - prev_ts, 3)
                data["count"] += 1
                data["prev_ts"] = now
        except cantools.database.DecodeError as e:
            print(f"{repr(e)}: {rx_msg.name}")
        except Exception as e:
            # this message is not for us
            pass
