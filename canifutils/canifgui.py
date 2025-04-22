import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import can
import cantools


class CanifGui:
    def __init__(self):
        self.displayed_cfg = {}
        self.displayed_signals = {}
        self.last_selected_msg = None
        self.vitals_tree = None
        self.responses_tree = None
        self.responses_combobox = None
        self.rx_msg_tree = None
        self.clock_label = None
        self.last_save_label = None
        self.root = None

    def _update_response_section(self, message):
        signals = self.sig_vals.get(message, {})
        for signal_name, signal_value in signals.items():
            iid = f"{message}_{signal_name}"

            # Check if the item exists before trying to update it
            if self.responses_tree.exists(iid):
                current_value = self.responses_tree.item(iid, "values")[1]
                if current_value != signal_value:
                    self.responses_tree.item(iid, values=(signal_name, signal_value))
            else:
                # If the signal doesn't exist in the treeview, add it
                self.responses_tree.insert(
                    "", "end", iid=iid, text=message, values=(signal_name, signal_value)
                )

    def _on_message_select(self, event):
        """
        Function to update the response signals when a message is selected
        """
        selected_message = self.responses_combobox.get()
        if selected_message:
            self.last_selected_msg = selected_message  # Store the selected message

            # Clear the current signals displayed in the responses treeview
            for item in self.responses_tree.get_children():
                self.responses_tree.delete(item)

            # Populate the response section with signals for the selected message
            self._update_response_section(selected_message)

    def _update_clock(self):
        current_time = time.strftime("%H:%M:%S")
        self.clock_label.config(text=current_time)
        self.clock_label.after(1000, self._update_clock)

    def _update_meas_gui(self):
        # Update the vitals section without flickering
        for msg, signals in self.vitals.items():
            timestamp = self.rx_msg_stats[msg]["last_received"]
            for signal_name, signal_value in signals.items():
                iid = f"{msg}_{signal_name}"

                # If the signal is already displayed, update its value
                if iid in self.displayed_signals:
                    self.vitals_tree.item(
                        iid, values=(signal_name, signal_value, timestamp)
                    )
                    self.displayed_signals[iid] = signal_value
                else:
                    # Insert a new signal if it doesn't exist
                    self.vitals_tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(signal_name, signal_value, timestamp),
                    )
                    self.displayed_signals[iid] = signal_value

        # Update the response section with available messages in the dropdown
        self.responses_combobox["values"] = list(self.rx_msg_stats.keys())

        # Update CAN message stats
        for message, stats in self.rx_msg_stats.items():
            message_iid = message
            last_received = stats["last_received"]
            cycle_time = stats["cycle_time"]
            received_count = stats["count"]

            # Check if the message already exists
            if not self.rx_msg_tree.exists(message_iid):
                self.rx_msg_tree.insert(
                    "",
                    "end",
                    iid=message_iid,
                    values=(message, last_received, cycle_time, received_count),
                )
            else:
                # Update the existing message stats
                self.rx_msg_tree.item(
                    message_iid,
                    values=(message, last_received, cycle_time, received_count),
                )

        # Preserve the last selected message in the dropdown
        if self.last_selected_msg:
            if self.last_selected_msg in self.sig_vals:
                self.responses_combobox.set(self.last_selected_msg)
                self._update_response_section(self.last_selected_msg)
            else:
                self.responses_combobox.set("Select a message")

        self.root.after(1000, self._update_meas_gui)

    def _send_estop(self, label):
        sig_dict = {}
        (db_msg, sig_name, sig_value) = self.estop_msg_sig_val
        for signal in db_msg.signals:
            if signal.name == sig_name:
                sig_dict[signal.name] = sig_value
                entry, var = self.displayed_cfg[db_msg.name][sig_name]
                display_value = signal.choices.get(sig_value)
                var.set(display_value)
                self.sig_vals[db_msg.name][signal.name] = sig_value
            else:
                sig_dict[signal.name] = self.sig_vals[db_msg.name][signal.name]
        self.send_can_message(db_msg, sig_dict)
        label.config(text=f'Last sent: {time.strftime("%H:%M:%S")}')

    def _get_cfg_val(self, signal: cantools.database.can.Signal, msg_name: str):
        entry, var = self.displayed_cfg[msg_name][signal.name]
        val = 0
        if signal.choices:
            var_str = var.get()
            # Reverse lookup in the choices dictionary
            for cval, cval_str in signal.choices.items():
                if cval_str == var_str:
                    val = cval
        else:
            try:
                val = float(entry.get())
            except ValueError:
                print(f"Invalid input: '{entry.get()}'")

        return val

    def _save_cfg_values(self, label):
        try:
            self.send_save_config_message()
        except NotImplementedError:
            self._write_config_file()
        label.config(text=f'Last save: {time.strftime("%H:%M:%S")}')

    def send_can_message(self):
        raise NotImplementedError(
            "Subclasses must implement the 'send_can_message' method."
        )

    def _send_cfg_message(self, msg: cantools.database.can.Message, label=None) -> None:
        # reset dict for every new message
        sig_dict = {}
        for signal in msg.signals:
            sig_dict[signal.name] = self._get_cfg_val(signal, msg.name)
            self.sig_vals[msg.name][signal.name] = sig_dict[signal.name]

        self.send_can_message(msg, sig_dict)
        if label:
            label.config(text=f'Last sent: {time.strftime("%H:%M:%S")}')

    def _send_all_cfg_messages(self, label):
        for msg in self.cfg_msg_list:
            self._send_cfg_message(msg)
        label.config(text=f'Last sent: {time.strftime("%H:%M:%S")}')

    def _create_editable_field(self, frame, row, col, signal, value):
        if signal.choices:
            sig_choice_text = [text for key, text in signal.choices.items()]
            sig_label = signal.name
        else:
            sig_label = f"{signal.name} [{signal.minimum}, {signal.maximum}]"
        label = tk.Label(frame, text=sig_label)
        label.grid(row=row, column=col, padx=(7, 0), pady=5, sticky="w")

        var = tk.StringVar()
        if signal.choices:
            # Find the string representation of the integer value
            display_value = signal.choices.get(value, str(value))
            var.set(display_value)
            entry = tk.OptionMenu(frame, var, *signal.choices.values())
        else:
            var.set(value)
            entry = tk.Entry(frame, textvariable=var)
        entry.grid(row=row, column=col + 1, padx=(0, 20), pady=0, sticky="w")

        return (entry, var)

    def _create_cfg_gui(self, cfg_window):
        cfg_window.title("Configurations")
        # Create a canvas to hold the entire UI and add a vertical scrollbar
        canvas = tk.Canvas(cfg_window)
        v_scrollbar = tk.Scrollbar(cfg_window, orient="vertical", command=canvas.yview)
        h_scrollbar = tk.Scrollbar(
            cfg_window, orient="horizontal", command=canvas.xview
        )
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        cfg_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=cfg_frame, anchor="nw")
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        cfg_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all"),
                width=e.width,  # Update canvas width to frame width
                height=e.height,  # Update canvas height to frame height
            ),
        )

        # Create the update button and message box
        last_send_all_label = tk.Label(cfg_frame, text="Last sent: None")
        send_all_button = tk.Button(
            cfg_frame,
            text="Send All",
            command=lambda: self._send_all_cfg_messages(last_send_all_label),
        )
        send_all_button.grid(row=0, column=0, padx=(5, 0), pady=0, sticky="w")
        last_send_all_label.grid(row=1, column=0, padx=(5, 0), pady=0, stick="w")

        # Create the save config button and message box
        last_save_label = tk.Label(cfg_frame, text="Last save: None")
        save_config_button = tk.Button(
            cfg_frame,
            text="Save config",
            command=lambda: self._save_cfg_values(last_save_label),
        )
        save_config_button.grid(row=0, column=1, padx=(5, 0), pady=0, sticky="w")
        last_save_label.grid(row=1, column=1, padx=(5, 0), pady=0, stick="w")

        # Create the e-stop button and message box
        if self.estop_msg_sig_val:
            estop_label = tk.Label(cfg_frame, text="Last sent: None")
            estop_button = tk.Button(
                cfg_frame,
                text="E-STOP",
                font=("Helvetica", 12, "bold"),
                command=lambda: self._send_estop(estop_label),
            )
            estop_button.config(fg="red", relief="raised")
            estop_button.grid(row=0, column=2, padx=(5, 0), pady=0, sticky="w")
            estop_label.grid(row=1, column=2, padx=(5, 0), pady=0, stick="w")

        quit_button = tk.Button(cfg_frame, text="Quit", command=self.close)
        quit_button.grid(row=0, column=3, padx=5, pady=0, stick="w")

        # start on the 2nd row
        curr_row = 2
        next_row = 2
        col = 0
        for msg in self.cfg_msg_list:
            title_label = tk.Label(
                cfg_frame, text=msg.name, font=("Helvetica", 12, "bold")
            )
            title_label.grid(row=curr_row, column=col, padx=5, pady=(20, 0), sticky="w")
            last_send_label = tk.Label(cfg_frame, text="Last sent: None")
            send_button = tk.Button(
                cfg_frame,
                text="Send",
                command=lambda m=msg, l=last_send_label: self._send_cfg_message(m, l),
            )
            send_button.grid(
                row=curr_row, column=col + 1, padx=(0, 5), pady=(20, 0), sticky="w"
            )
            last_send_label.grid(
                row=curr_row + 1, column=col, padx=5, pady=0, stick="w"
            )
            self.displayed_cfg[msg.name] = {}
            row = curr_row + 2
            # loop to add all the signals for this message
            for signal in msg.signals:
                (entry, var) = self._create_editable_field(
                    frame=cfg_frame,
                    row=row,
                    col=col,
                    signal=signal,
                    value=self.sig_vals[msg.name][signal.name],
                )
                self.displayed_cfg[msg.name][signal.name] = (entry, var)
                row += 1
                next_row = max(row, next_row)

            col += 2
            col = col % 4
            if col == 0:
                curr_row = next_row
            else:
                row = curr_row

        cfg_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def _create_meas_gui(self, root):
        root.title("Measurements")

        # Section 1: Vitals
        vitals_frame = tk.Frame(root)
        vitals_frame.pack(padx=10, pady=10, fill="both", expand=True)

        vitals_label = tk.Label(vitals_frame, text="Vitals", font=("Helvetica", 16))
        vitals_label.pack()

        vitals_tree = ttk.Treeview(
            vitals_frame, columns=("Signal", "Value", "Last Received"), show="headings"
        )
        vitals_tree.heading("Signal", text="Signal")
        vitals_tree.heading("Value", text="Value")
        vitals_tree.heading("Last Received", text="Last Received")
        vitals_tree.pack(fill="both", expand=True)
        self.vitals_tree = vitals_tree

        # Section 2: Responses
        responses_frame = tk.Frame(root)
        responses_frame.pack(padx=10, pady=10, fill="both", expand=True)

        responses_label = tk.Label(
            responses_frame, text="Responses", font=("Helvetica", 16)
        )
        responses_label.pack()

        responses_combobox = ttk.Combobox(responses_frame)
        responses_combobox.pack(fill="x", padx=10, pady=5)
        responses_combobox.bind("<<ComboboxSelected>>", self._on_message_select)
        self.responses_combobox = responses_combobox

        responses_tree = ttk.Treeview(
            responses_frame, columns=("Signal", "Value"), show="headings"
        )
        responses_tree.heading("Signal", text="Signal")
        responses_tree.heading("Value", text="Value")
        responses_tree.pack(fill="both", expand=True)
        self.responses_tree = responses_tree

        # Section 3: CAN Messages Stats (Last Received, Cycle Time, Count)
        rx_msg_frame = tk.Frame(root)
        rx_msg_frame.pack(padx=10, pady=10, fill="both", expand=True)

        rx_msg_label = tk.Label(
            rx_msg_frame, text="CAN Messages Stats", font=("Helvetica", 16)
        )
        rx_msg_label.pack()

        rx_msg_tree = ttk.Treeview(
            rx_msg_frame,
            columns=("Message", "Last Received", "Cycle Time", "Count"),
            show="headings",
        )
        rx_msg_tree.heading("Message", text="Message")
        rx_msg_tree.heading("Last Received", text="Last Received")
        rx_msg_tree.heading("Cycle Time", text="Cycle Time")
        rx_msg_tree.heading("Count", text="Count")
        rx_msg_tree.pack(fill="both", expand=True)
        self.rx_msg_tree = rx_msg_tree

        # Clock in the top-right corner (use place to precisely position it)
        clock_label = tk.Label(root, font=("Helvetica", 12))
        clock_label.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        self.clock_label = clock_label

        # Start the clock update function
        self._update_clock()
        self._update_meas_gui()

    def _create_gui(self):
        self.root = tk.Tk()
        cfg_window = tk.Toplevel(self.root)
        cfg_window.transient(self.root)

        self._create_meas_gui(self.root)
        self._create_cfg_gui(cfg_window)

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        tk.Button(self.root, text="Quit", command=self.close).pack()

        # Launch GUI
        self.root.mainloop()

    def launch(self):
        if not self.root:
            self._create_gui()

    def close(self):
        if self.root:
            self.root.destroy()
            self.root = None
