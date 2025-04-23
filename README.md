# canifutils

**canifutils** is a Python package for visualizing, interacting with, and managing CAN communication using a GUI or terminal. It wraps around `python-can` and `cantools` to provide a simple way to inspect and send CAN messages.

## Features
- Live GUI with vitals, stats, and message configuration
- Terminal interface for quick access over SSH or headless
- Logging, emergency-stop, and periodic message updates
- CLI support for launching the GUI

## Not supported
- Multiplexed messages (not tested)
- Bus error handling and reconnection

## Installation

```bash
pip install canifutils
```

## Usage

Example usage can be found in the canif_cli file.


## Test

The command below will load a GUI using messages from the provided dbc with the Node
used to figure out transmit and receive messages.
The estop functionality is optional and provides a quick method to send a disable
message.

```bash
canifutilstest -d path/to/your.dbc -n Node -e estopMsg estopSignal estopValue
```

