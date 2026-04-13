from enum import Enum


class Intent(str, Enum):
    AFFIRM = "AFFIRM"
    DENY = "DENY"
    INFORM = "INFORM"
    REQUEST = "REQUEST"
    ASK = "ASK"
    OBJECT = "OBJECT"
    COMPLAIN = "COMPLAIN"
    ESCALATE = "ESCALATE"
    DEFER = "DEFER"
    ELABORATE = "ELABORATE"
    GREET = "GREET"
    THANK = "THANK"
    GOODBYE = "GOODBYE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNCLEAR = "UNCLEAR"
