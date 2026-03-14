import pandas as pd


class Save_As:
    def __init__(self) -> None:
        return None

    def to_excel(self, source_path: str, dest_path: str):
        self.process("excel", source_path, dest_path)

    def to_json(self, source_path: str, dest_path: str):
        self.process("json", source_path, dest_path)

    def process(self, to: str, source_path: str, dest_path: str):
        match to:
            case "excel":
                df = pd.read_csv(source_path)
                df.to_excel(dest_path, index=False)
            case "json":
                df = pd.read_csv(source_path)
                df.to_json(dest_path, orient="records")
