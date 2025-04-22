# canifutils

**canifutils** is a Python package for visualizing, interacting with, and managing CAN interfaces using a GUI or terminal-based interface. It wraps around `python-can` and `cantools` to provide a simple way to inspect and send CAN messages.

## Features

- Live GUI with vitals, stats, and message configuration
- Terminal interface for quick access over SSH or headless
- Logging, emergency-stop, and periodic message updates
- CLI support for launching the GUI

## Installation

```bash
pip install canifutils

## Usage
'''bash
canifutils -d path/to/your.dbc -r ReceiverNode -e estopMsg estopSignal estopValue

