import threading
import time
from queue import SimpleQueue

import can
import cantools


class CanifTerm:
    """
    Implements a terminal interface to send and receive CAN
    messages.

    The user must provide a 'sig_val' dictionary with all the message names
    as keys to a dictionary of signal names and values.
    The user is responsible for updating this dictionary with received CAN
    values.
    """

    def __init__(self, event: threading.Event):
        self.periodic: threading.Thread = threading.Thread(
            target=self._periodic_refresh
        )
        self.ui_update_period = 0
        self.ui_running = False
        self.event = event

    def _periodic_refresh(self):
        run = True
        update_timeout = 0
        while run:
            try:
                if self.ui_update_period > 0:
                    if update_timeout < 0:
                        self._print_measurement_signals()
                        update_timeout = self.ui_update_period
                    else:
                        time.sleep(1)
                        update_timeout -= 1
                elif self.ui_update_period == 0:
                    # periodic thread stopped. wait for new event.
                    self.event.wait()
                    self.event.clear()
                    update_timeout = self.ui_update_period
                else:
                    # negative update period is an exit request
                    run = False
            except Exception as e:
                print(repr(e))

    def _print_measurement_signals(self):
        print("\n")
        for msg in self.db.messages:
            if msg.name in self.vitals.keys():
                for sig in msg.signals:
                    if sig.choices:
                        val = sig.choices[self.sig_vals[msg.name][sig.name]].name
                    else:
                        val = self.sig_vals[msg.name][sig.name]
                    print(f"{sig.name}: {val}")
        print("\n>")

    def _get_message_from_database(self, msg_id):
        """
        Looks for a message from the message name or ID
        Example: EPC_status_Address001 or 15400961
        """
        msg = None
        try:
            frame_id = int(msg_id)
            msg = self.db.get_message_by_frame_id(frame_id)
        except ValueError:
            try:
                msg = self.db.get_message_by_name(msg_id)
            except ValueError:
                raise KeyError(f"Invalid msg id '{msg_id}'")
            except:
                raise
        except KeyError:
            raise KeyError(f"Invalid msg id '{msg_id}'")
        except Exception as e:
            print(repr(e))
            raise
        finally:
            return msg

    def _print_message_signals(self, msg, choices=False):
        """
        Prints detailed message info including signals
        """
        print(
            f"{msg.name}: ID={msg.frame_id}:{hex(msg.frame_id)} Signals={len(msg.signals)}"
        )

        s_choices = ""
        for signal in msg.signals:
            if signal.choices:
                val = signal.choices[self.sig_vals[msg.name][signal.name]]
                val = f"{val.value}: {val.name}"
                for k, v in signal.choices.items():
                    s_choices += f' {k}: "{v}",'
            else:
                val = self.sig_vals[msg.name][signal.name]
                s_choices = f"{signal.minimum}, {signal.maximum}"
            s = f'\t{signal.name} "{val}"'
            if choices:
                s += f" [{s_choices}]"

            print(s)

    def _list_config_signals(self):
        """
        Prints configuration message details for given ID or entire database
        """
        try:
            for message in self.db.messages:
                if message.frame_id in self.rx_ids:
                    continue
                self._print_message_signals(msg=message, choices=True)
        except KeyError as e:
            print(repr(e) + f" Invalid message name: {msg_id}")
        except ValueError as e:
            print(repr(e) + f" Invalid frame id: {msg_id}")
        except:
            raise

    def _list_meas_signals(self):
        """
        Prints measurement message details for given ID or entire database
        """
        try:
            for message in self.db.messages:
                if message.frame_id not in self.rx_ids:
                    continue
                self._print_message_signals(message)
        except KeyError as e:
            print(repr(e) + f" Invalid message name: {msg_id}")
        except ValueError as e:
            print(repr(e) + f" Invalid frame id: {msg_id}")
        except:
            raise

    def _set_message(self, msg_id, msg_sigvals):
        """
        Sets message signals in configuration dictionary and returns packed CAN
        message with new signal data
        """
        msg = self._get_message_from_database(msg_id)
        if not msg:
            raise KeyError(f"Invalid msg id: {msg_id}")
        msg_name = msg.name
        signals = [signal.name for signal in msg.signals]

        if (len(msg_sigvals) / 2) != len(signals):
            raise LookupError(
                f"Expected {len(msg.signals)} but received {len(signals)} signals"
            )

        if msg.frame_id in self.rx_ids:
            raise IndexError(
                f"Trying to set response message: {hex(msg.frame_id)} {msg.name}"
            )

        sig_dict = {}  # used to create an encoded CAN message
        for i, s in enumerate(msg_sigvals[::2]):
            if s in signals:
                signals.remove(s)
                val = float(msg_sigvals[2 * i + 1])
                sig_dict[s] = val
                self.sig_vals[msg_name][s] = val
            else:
                raise ValueError(f"Duplicate or invalid signal: {s}")

        self.send_can_message(msg=msg, sig_dict=sig_dict)

    def _print_message(self, msg_id):
        """
        Returns signal values for given message ID
        """
        msg = self._get_message_from_database(msg_id)
        self._print_message_signals(msg=msg, choices=(msg.frame_id in self.rx_ids))

    def _print_help_menu(self):
        print("Command list:")
        print("\th Print help menu")
        print(
            "\ts <msg_id|msg_name> <signal_name val signal_name val ...>\n\
            Send message (must populate all signals. See 'u')"
        )
        print("\td Print database")
        print("\tp <msg_id|msg_name> Print message details")
        print("\tpp <#> Periodic measurement print period in seconds")
        print("\tdc Print all config messages from database")
        print("\tdm Print all response messages from database")
        print("\tq Quit")
        print("\tsave Save config file with current config")

    def _get_user_input(self):
        self.ui_running = True
        self.periodic.start()
        while self.ui_running:
            try:
                cmd = input("> ").split(" ")

                if cmd[0] == "h":
                    self._print_help_menu()
                elif cmd[0] == "d":
                    self._list_config_signals()
                    self._list_meas_signals()
                elif cmd[0] == "dc":
                    self._list_config_signals()
                elif cmd[0] == "dm":
                    self._list_meas_signals()
                elif cmd[0] == "p":
                    if len(cmd) < 2:
                        raise TypeError("Insufficient arguments")
                    self._print_message(cmd[1])
                elif cmd[0] == "pp":
                    if len(cmd) != 2:
                        raise TypeError("Update period not given")
                    try:
                        val = int(cmd[1])
                        if val < 0:
                            raise ValueError
                    except:
                        raise ValueError(f"Invalid period: '{cmd[1]}'")
                    else:
                        self.ui_update_period = val
                        self.event.set()
                elif cmd[0] == "s":
                    if len(cmd) < 4:
                        raise TypeError("Insufficient arguments")
                    self._set_message(cmd[1], cmd[2:])
                elif cmd[0] == "q":
                    self.close()
                elif cmd[0] == "save":
                    self.send_save_config_message()
            except Exception as e:
                print(repr(e))

        # close periodic thread
        prd = self.ui_update_period
        self.ui_update_period = -1  # set exit signal
        # wake thread if stopped
        if prd == 0:
            self.event.set()
        self.periodic.join()

    def _get_cfg_val(self, signal: cantools.database.can.Signal, msg_name: str):
        """
        class CanInterface override
        Get the config signal value for the interface to write
        to a config file
        """
        return self.sig_vals[msg_name][signal.name]

    def launch(self):
        self._get_user_input()

    def close(self):
        self.ui_running = False


def main():
    from epccontrol import EpcControl
    from epcinterface import EpcInterface

    db = cantools.database.load_file(EpcInterface.default_dbc_path)
    sig_vals = EpcControl.create_signal_dictionary(db)
    cmd_queue: SimpleQueue[can.Message] = SimpleQueue()
    epcif = EpcInterface(database=db, cmd_queue=cmd_queue, sig_vals=sig_vals, term=True)

    epcif._get_user_input()

    while not epcif.cmd_queue.empty():
        msg = epcif.cmd_queue.get()
        msg_id = msg.arbitration_id
        if msg_id == epcif.special_cmd_mid:
            decoded_data = msg.data
        else:
            db_msg = db.get_message_by_frame_id(msg_id)
            decoded_data = db_msg.decode(msg.data, decode_choices=False)
        print(msg_id, decoded_data)


if __name__ == "__main__":
    main()
