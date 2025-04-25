import argparse
import base64

import cantools
import pandas as pd


class CanifCsvDecoder:
    def __init__(self, dbc_file: str, csv_file: str, enum: int = 0):
        self.dbc_file = dbc_file
        self.enum = enum
        self.csv_file = csv_file
        self.db = cantools.database.load_file(dbc_file)
        self.df = pd.read_csv(csv_file)
        self.decoded_df = None

    def decode(self) -> pd.DataFrame:
        decoded_rows = []

        for _, row in self.df.iterrows():
            try:
                arbitration_id = int(row["arbitration_id"], 16) - self.enum
                data_bytes = base64.b64decode(row["data"])
                message = self.db.get_message_by_frame_id(arbitration_id)

                if message:
                    decoded_signals = message.decode(data_bytes)
                    decoded_rows.append(
                        {
                            "timestamp": row["timestamp"],
                            "arbitration_id": hex(arbitration_id + self.enum),
                            **decoded_signals,
                        }
                    )
            except Exception as e:
                print(f"[WARN] Skipping row due to error: {e}")

        self.decoded_df = pd.DataFrame(decoded_rows)
        return self.decoded_df

    def to_csv(self, output_file: str = "decoded_output.csv"):
        if self.decoded_df is not None:
            self.decoded_df.to_csv(output_file, index=False)
            print(f"[INFO] Decoded data saved to '{output_file}'")
        else:
            print("[ERROR] No decoded data. Run decode() first.")


def main():
    parser = argparse.ArgumentParser(description="Decode CAN log CSV using DBC file.")
    parser.add_argument("--dbc", required=True, help="Path to DBC file")
    parser.add_argument(
        "--enum",
        required=False,
        help="Enumeration offset for nodes",
        type=int,
        default=0,
    )
    parser.add_argument("--csv", required=True, help="Path to CAN log CSV file")
    parser.add_argument("--out", required=True, help="Output CSV file path")

    args = parser.parse_args()

    decoder = CanifCsvDecoder(args.dbc, args.csv, args.enum)
    decoder.decode()
    decoder.to_csv(args.out)


if __name__ == "__main__":
    main()
