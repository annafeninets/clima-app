from dataclasses import dataclass


@dataclass(slots=True)
class Preferences:
    style: str = ""
    colors: str = ""
    sizes: str = ""
    bodyFeatures: str = ""
