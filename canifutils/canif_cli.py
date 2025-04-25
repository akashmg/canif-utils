import argparse
import datetime
import os
import threading
import time
from pathlib import Path

import can
import cantools

from .canif import Canif
from .caniflistener import CanifListener


def get_args():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = Path("logs") / f"{timestamp}-cangui.csv"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--canbusif",
        help="CAN bus interface '-c pcan PCAN_USBBUS1'",
        nargs=2,
        required=False,
        default=["virtual", "vcan0"],
    )
    parser.add_argument("-d", "--dbc_file", help="CAN DBC file", required=True)
    parser.add_argument(
        "-l",
        "--log",
        type=str,
        nargs="?",
        const=log_path,
        default=None,
        help='Set for logging. Optional to add a file path arg.\n\
        Default path is "./logs/%Y-%m-%d_%H-%M-%S-cangui.log',
        required=False,
    )
    parser.add_argument(
        "-v",
        "--vitals",
        nargs="+",
        help="List of message names to display in the vitals section.\
            Example: -v MSG1 MSG2 MSG3",
        required=False,
    )
    parser.add_argument("-n", "--node", help="Node to emulate", required=False)
    parser.add_argument(
        "-e",
        "--estop",
        nargs=3,
        help="'-e msg sig val' (Send disable)",
        default=None,
        required=False,
    )
    parser.add_argument(
        "-t",
        "--test",
        help="Send test messages to node for display",
        required=False,
        action="store_true",
    )

    return parser.parse_args()


def send_test_messages(args, database, bus, test_stop_event):
    count = 0
    val = 0
    send_message = False
    while not test_stop_event.is_set():
        if count == 5:
            val = 1
            send_message = True
        elif count == 10:
            count = 0
            send_message = True
        else:
            val = 0
            send_message = False

        count += 1

        for msg in database.messages:
            if args.node in msg.receivers and send_message:
                sig_dict = {}
                for sig in msg.signals:
                    sig_dict[sig.name] = val
                data = msg.encode(sig_dict)
                can_msg = can.Message(arbitration_id=msg.frame_id, data=data)
                bus.send(can_msg)

        time.sleep(1)


def main():
    args = get_args()
    database = cantools.database.load_file(args.dbc_file)
    db_name = os.path.splitext(os.path.basename(args.dbc_file))[0]
    sig_dict = Canif.get_sig_dict_from_config()
    Canif.init_sig_dict(sig_dict=sig_dict, db=database)

    if args.estop:
        estop_msg_sig_val = (
            database.get_message_by_name(args.estop[0]),
            args.estop[1],
            int(args.estop[2]),
        )
    else:
        estop_msg_sig_val = None

    can_notifier = None
    test_stop_event = None
    test_thread = None
    try:
        with can.Bus(
            interface=args.canbusif[0],
            channel=args.canbusif[1],
            receive_own_messages=True,
        ) as bus:
            gui = Canif(
                sig_vals=sig_dict,
                node=args.node,
                vitals_msgs=args.vitals,
                estop_msg_sig_val=estop_msg_sig_val,
                bus=bus,
                database=database,
                use_term=False,
            )
            can_listener = CanifListener(
                sig_vals=sig_dict, database=database, rx_msg_stats=gui.rx_msg_stats
            )
            listeners = [can_listener]
            if args.log:
                Path(args.log).parent.mkdir(parents=True, exist_ok=True)
                log_writer = can.Logger(args.log)
                listeners.append(log_writer)
            can_notifier = can.Notifier(bus, listeners)

            # test framework
            if args.test:
                test_stop_event = threading.Event()
                test_thread = threading.Thread(
                    target=send_test_messages,
                    args=(args, database, bus, test_stop_event),
                )
                test_thread.start()

            # blocking call while the gui is running
            gui.launch()

            can_notifier.stop()
            test_stop_event.set()
            test_thread.join()

    except Exception as e:
        print(repr(e))
    finally:
        if can_notifier:
            can_notifier.stop()
        if args.test:
            if test_stop_event:
                test_stop_event.set()
            if test_thread:
                test_thread.join()


if __name__ == "__main__":
    main()
