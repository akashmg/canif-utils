import json
import threading
from pathlib import Path

import can
import cantools

from .canifgui import CanifGui
from .canifterm import CanifTerm


class Canif(CanifGui, CanifTerm):

    """
    Creates the GUI elements to send and receive CAN messages. This class
    provides methods for initializing the GUI, updating displayed values,
    sending CAN messages, and saving/loading default transmit signal values.
    It is designed to work with a CAN bus, a CAN database, and a configuration file.
    """

    @classmethod
    def get_sig_dict_from_config(cls, fcfg_path: str = None):
        sig_dict = {}
        if fcfg_path is None:
            fcfg_path = Path("data") / f"cangui_config_params.csv"

        if fcfg_path.exists():
            try:
                with open(fcfg_path, "r") as fcfg:
                    sig_dict = json.load(fcfg)
                print(f"Read config from {fcfg_path}")
            except FileNotFoundError:
                print(f"Config file not found at {fcfg_path}")
            except json.JSONDecodeError:
                print("Error reading configuration file")

        return sig_dict

    @classmethod
    def init_sig_dict(cls, sig_dict: dict, db: cantools.database.can.Database) -> None:
        for message in db.messages:
            if message.name in sig_dict:
                cfg_sigs = sig_dict[message.name]
            else:
                sig_dict[message.name] = {}
                cfg_sigs = None

            for signal in message.signals:
                val = signal.initial if signal.initial else 0
                if cfg_sigs and signal.name in cfg_sigs:
                    sig_dict[message.name][signal.name] = cfg_sigs[signal.name]
                else:
                    sig_dict[message.name][signal.name] = val

    def __init__(
        self,
        sig_vals: dict[str, dict[str, int]],
        vitals_msgs: list[str],
        rx_ids: set[int] = None,
        estop_msg_sig_val: tuple[cantools.database.can.Message, str, int] = None,
        bus: can.BusABC = None,
        database: cantools.database.can.Database = None,
        use_term: bool = False,
        event: threading.Event = None,
    ):
        self.sig_vals: dict[str, dict[str, int]] = sig_vals
        self.vitals_msgs: list[str] = vitals_msgs
        self.rx_ids: set[int] = rx_ids
        self.estop_msg_sig_val: tuple[
            cantools.database.can.Message, str, int
        ] = estop_msg_sig_val
        self.bus: can.BusABC = bus
        self.db: cantools.database.can.Database = database
        self.cfg_msg_list: list[cantools.database.can.Message] = [
            msg for msg in self.db.messages if msg.frame_id not in self.rx_ids
        ]
        # db messages are sorted from high MID to low
        # we want this list to be low to high
        self.cfg_msg_list.reverse()
        cfg_msg_names = [msg.name for msg in self.cfg_msg_list]
        self.rx_msg_stats: dict = {}
        for msg in self.sig_vals.keys():
            if msg not in cfg_msg_names:
                self.rx_msg_stats[msg] = {
                    "last_received": 0,
                    "cycle_time": 0,
                    "count": 0,
                    "prev_ts": 0,
                }
        self.vitals: dict = {}
        for msg in vitals_msgs:
            self.vitals[msg] = self.sig_vals[msg]
        self.use_term: bool = use_term

        if self.use_term:
            CanifTerm.__init__(self, event=event)
        else:
            CanifGui.__init__(self)

    def send_can_message(self, msg: cantools.database.can.Message, sig_dict: dict):
        """
        This method should be overridden by derived classes
        to provide specific functionality.
        """
        if self.bus:
            try:
                can_data = msg.encode(sig_dict)
                can_msg = can.Message(arbitration_id=msg.frame_id, data=can_data)
                self.bus.send(can_msg)
            except can.CanError as e:
                print(repr(e))

        else:
            raise NotImplementedError(
                "Subclasses must implement the 'send_can_message' method."
            )

    def send_save_config_message(self):
        """
        This method should be overridden by derived classes
        to provide specific functionality.
        """
        raise NotImplementedError(
            "Subclasses must implement the 'send_save_config_message' method."
        )

    def _write_config_file(self):
        cfg_vals = {}
        for msg in self.cfg_msg_list:
            # reset for every new message
            sig_dict = {}
            for signal in msg.signals:
                sig_dict[signal.name] = self._get_cfg_val(signal, msg.name)

            cfg_vals[msg.name] = sig_dict

        fcfg_path = Path("data") / f"cangui_config_params.csv"
        Path(fcfg_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(fcfg_path, "w") as fcfg:
                json.dump(cfg_vals, fcfg, indent=4)
            print("Wrote updated params to config file")
        except Exception as e:
            print("Error: Failed to write new params to config file" + repr(e))

    """
    Base class overrides
    """

    def launch(self):
        if self.use_term:
            CanifTerm.launch(self)
        else:
            CanifGui.launch(self)

    def close(self):
        if self.use_term:
            CanifTerm.close(self)
        else:
            CanifGui.close(self)
